"""F3 runtime composition: OFF by default, guarded mount and real ledger read."""
from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_command_quota_readback import (
    PATH,
    SCHEMA,
    sign_command_quota_readback,
)
from core.ai_control_plane import ControlPlaneBase
from core.ai_plan_usage_guard import PlanQuotaPolicy
from core.ai_quota_store import QuotaDenied, QuotaReservations
from core.ai_service_api import create_app
from core.ai_service_settings import CoreEnvironment, CoreSettings

SERVICE_KEY = "synthetic-fm-core-runtime-service-secret-12345"
ASSISTANT_KEY = "synthetic-fm-assistant-core-plan-key-123456"
COMMAND_KEY = "synthetic-fm-command-core-readback-key-123456"


def settings(database: str, **overrides):
    values = {
        "environment": CoreEnvironment.TEST,
        "service_key": SERVICE_KEY,
        "routes": (),
        "control_plane_database_url": database,
        "assistant_plan_url": "https://assistant.example.test",
        "assistant_plan_signing_key": ASSISTANT_KEY,
    }
    values.update(overrides)
    return CoreSettings(**values)


def routes(app):
    return [getattr(r, "path", None) for r in app.router.routes]


def test_readback_route_is_not_registered_without_explicit_opt_in(tmp_path):
    config = settings(f"sqlite:///{tmp_path / 'off.db'}")
    app = create_app(config)
    assert PATH not in routes(app)
    assert config.command_quota_readback_secret is None
    assert config.command_quota_readback_enabled is False
    assert "command_quota_authority" not in app.state._state


def test_incomplete_reused_or_accidentally_set_keys_fail_closed(tmp_path):
    db = f"sqlite:///{tmp_path / 'settings.db'}"
    cases = (
        {"command_quota_readback_secret": COMMAND_KEY},
        {"command_quota_readback_enabled": True},
        {"command_quota_readback_enabled": True,
         "command_quota_readback_secret": "too-short"},
        {"command_quota_readback_enabled": True,
         "command_quota_readback_secret": ASSISTANT_KEY},
        {"command_quota_readback_enabled": True,
         "command_quota_readback_secret": SERVICE_KEY},
        {"command_quota_readback_enabled": True,
         "command_quota_readback_secret": COMMAND_KEY,
         "assistant_plan_url": None},
    )
    for case in cases:
        with pytest.raises(RuntimeError):
            create_app(settings(db, **case))


class FreshPolicy:
    def __init__(self):
        self.active = True
        self.reads = 0

    def resolve(self, *, tenant_id, unit_id, capability, now):
        self.reads += 1
        if (not self.active or tenant_id != "tenant-fm"
            or unit_id != "unit-fm"
            or capability != "atendimento_interpretacao"):
            raise QuotaDenied("synthetic_policy_denied")
        return PlanQuotaPolicy(
            tenant_id=tenant_id, unit_id=unit_id, plan_code="BASICO",
            revision=3, valid_until=now + timedelta(seconds=35),
            input_bound=20, output_bound=20,
            scopes=(("ai.requests", "tenant"),
                    ("ai.total_tokens", "tenant")),
            grants=(("ai.requests", "tenant", 10, 86400),
                    ("ai.total_tokens", "tenant", 500, 86400)),
        )


def send(client: TestClient, body: dict):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return client.post(PATH, content=raw, headers={
        "Content-Type": "application/json",
        "X-FM-Command-Quota-Signature": sign_command_quota_readback(
            secret=COMMAND_KEY.encode(), body=raw,
        ),
    })


def test_live_runtime_mount_uses_current_authority_and_existing_ledger(tmp_path):
    filename = tmp_path / "runtime.db"
    db = f"sqlite:///{filename}"
    engine = create_engine(db)
    ControlPlaneBase.metadata.create_all(engine)
    try:
        app = create_app(settings(
            db, command_quota_readback_enabled=True,
            command_quota_readback_secret=COMMAND_KEY,
        ))
        assert routes(app).count(PATH) == 1
        policy = FreshPolicy()
        quota = QuotaReservations(
            sessionmaker(bind=engine, expire_on_commit=False)
        )
        quota.project_signed_grants(
            tenant_id="tenant-fm", unit_id="unit-fm", revision=3,
            grants=(("ai.requests", "tenant", 10, 86400),
                    ("ai.total_tokens", "tenant", 500, 86400)),
        )
        # In this isolated mount test, inject the same dependencies that the
        # actual application lifespan initializes from build_persistent_core.
        app.state.command_quota_authority = policy
        app.state.command_quota_ledger = quota
        client = TestClient(app)
        body = {
            "schema": SCHEMA, "tenant_id": "tenant-fm",
            "unit_id": "unit-fm",
            "capability": "atendimento_interpretacao",
            "issued_at": int(datetime.now(UTC).timestamp()),
            "nonce": secrets.token_urlsafe(24),
        }
        good = send(client, body)
        assert good.status_code == 200, good.text
        assert good.json()["license_freshly_verified"] is True
        assert good.json()["core_policy_matches_signed_grant"] is True
        assert good.json()["reservation_created"] is False
        assert good.json()["case_resolved"] is False
        assert send(client, dict(body, tenant_id="unrelated")).status_code == 409
        policy.active = False
        assert send(client, body).status_code == 409
        policy.active = True
        del app.state.command_quota_authority
        assert send(client, body).status_code == 409
        assert policy.reads == 3
        before = quota.usage_snapshot(
            tenant_id="tenant-fm", unit_id="__tenant__",
            capability="ai.total_tokens", at=datetime.now(UTC),
        )
        assert before.reserved_units == 0
    finally:
        engine.dispose()
