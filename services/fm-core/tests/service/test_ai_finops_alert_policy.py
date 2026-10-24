"""F3 corporate alert configuration: transactional, signed, adversarial."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.ai_admin_audit import CommandAdminAuditRecord
from core.ai_command_authority import CommandTrustPolicy, VerifiedCommandAdmin
from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_finops_alert_outbox import AIFinOpsAlertOutboxRecord
from core.ai_finops_policy_api import finops_alert_policy_router
from core.ai_finops_policy_store import (
    AIFinOpsAlertPolicyRecord,
    PersistentFinOpsAlertPolicies,
)


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'alerts.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    yield PersistentFinOpsAlertPolicies(sessions), sessions
    engine.dispose()


def principal(jti="synthetic-jti-unique-0123456789"):
    return VerifiedCommandAdmin(
        user_id="human-fm", session_id="fm-session", token_id=jti,
        issued_at=100, expires_at=200, step_up_at=100,
        permissions=frozenset({"core.ai.admin.mutate"}),
    )


def set_policy(store, *, jti="synthetic-jti-unique-0123456789", expected=0, **change):
    data = {"tenant_id": "tenant-a", "unit_id": "unit-a",
            "expected_revision": expected, "enabled": True,
            "currency": "USD", "maximum_known_cost": Decimal("0.05"),
            "principal": principal(jti)}
    data.update(change)
    return store.update(**data)


def test_policy_cas_audit_scope_replay_and_disable_atomic(store):
    policies, sessions = store
    assert policies.get(tenant_id="tenant-a", unit_id="unit-a") is None
    result = set_policy(policies)
    assert result.revision == 1 and result.enabled
    assert policies.get(tenant_id="tenant-a", unit_id="other-unit") is None
    assert policies.get(tenant_id="foreign", unit_id="unit-a") is None
    with pytest.raises(ControlPlaneError, match="alert_revision_conflict"):
        set_policy(policies, jti="another-unique-jti-00000")
    with pytest.raises(ControlPlaneError, match="replayed"):
        set_policy(policies, expected=1)
    assert policies.get(tenant_id="tenant-a", unit_id="unit-a").revision == 1
    updated = set_policy(
        policies, jti="third-unique-jti-0000000", expected=1,
        enabled=False, maximum_known_cost=Decimal(10),
    )
    assert updated.revision == 2 and not updated.enabled
    with sessions() as db:
        rows = db.scalars(select(CommandAdminAuditRecord)).all()
        assert len(rows) == 2
        assert all(row.action == "finops.alert_policy.update" for row in rows)
        assert len(db.scalars(select(AIFinOpsAlertPolicyRecord)).all()) == 1


@pytest.mark.parametrize("changes", [
    {"enabled": 1},
    {"currency": "usd"},
    {"currency": "DOLLAR"},
    {"maximum_known_cost": Decimal("NaN")},
    {"maximum_known_cost": Decimal("Infinity")},
    {"maximum_known_cost": Decimal(0)},
    {"maximum_known_cost": Decimal("-0.1")},
    {"maximum_known_cost": Decimal(1000000001)},
    {"tenant_id": "foreign tenant"},
    {"expected_revision": True},
    {"expected_revision": -1},
    {"principal": replace(principal(), permissions=frozenset())},
])
def test_policy_rejects_malformed_or_unauthorized_mutations(store, changes):
    policies, _ = store
    with pytest.raises(ControlPlaneError):
        set_policy(policies, **changes)


def test_http_requires_both_service_identity_and_recent_human_step_up(store, monkeypatch):
    from fastapi import FastAPI

    policies, sessions = store
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    trust = CommandTrustPolicy(
        issuer="fm-command", audience="fm-core-recovery", public_key_pem=public,
    )
    transport = "synthetic-independent-command-service-key-123456789"
    app = FastAPI()
    app.state.control_plane_engine = sessions.kw["bind"]
    app.include_router(finops_alert_policy_router(trust=trust, transport_key=transport))
    body = {
        "tenant_id": "tenant-a", "unit_id": "unit-a", "expected_revision": 0,
        "enabled": True, "currency": "USD", "maximum_known_cost": "0.05",
    }
    path = "/internal/v1/command/ai/finops/alert-policy"
    now = int(datetime.now(UTC).timestamp())

    def jwt_for(jti, **overrides):
        claims = {
            "iss": "fm-command", "aud": "fm-core-recovery", "sub": "fm-admin",
            "jti": jti, "session_id": "fm-session", "iat": now, "nbf": now, "exp": now + 120,
            "step_up_at": now, "actor_type": "human", "role": "platform_admin",
            "scope": "fm_core_platform", "permissions": ["core.ai.admin.mutate"],
        }
        claims.update(overrides)
        return jwt.encode(claims, private, algorithm="RS256")

    headers = {
        "X-FM-Recovery-Service-Key": transport,
        "Authorization": "Bearer " + jwt_for("synthetic-write-jti-12345"),
    }
    http = TestClient(app)
    assert http.post(path, json=body).status_code == 401
    assert http.post(path, json=body, headers={
        "Authorization": headers["Authorization"],
    }).status_code == 401
    assert http.post(path, json=body, headers={
        **headers, "X-FM-Recovery-Service-Key": "wrong",
    }).status_code == 401
    assert http.post(path, json=body, headers={
        **headers, "Authorization": "Bearer " +
        jwt_for("wrong-role-jti-1234567", role="tenant_owner"),
    }).status_code == 403
    for value in (True, 0.0, "1", None):
        assert http.post(path, json={**body, "expected_revision": value},
                         headers=headers).status_code == 422
    for value in ("NaN", "-1", "Infinity", "0", "1e2", "0.0000000000001"):
        assert http.post(path, json={**body, "maximum_known_cost": value},
                         headers=headers).status_code == 422
    assert http.post(path, json=body, headers=headers).status_code == 204
    assert policies.get(tenant_id="tenant-a", unit_id="unit-a").revision == 1
    assert http.post(path, json={**body, "expected_revision": 1},
                     headers=headers).status_code == 409
    assert policies.get(tenant_id="tenant-a", unit_id="unit-a").revision == 1

    scan_path = "/internal/v1/command/ai/finops/alert-scan"
    scan_body = {
        "tenant_id": "tenant-a", "unit_id": "unit-a",
        "start_date": "2026-10-01", "end_date": "2026-10-22", "limit": 20,
    }
    assert http.post(scan_path, json=scan_body).status_code == 401
    assert http.post(
        scan_path, json=scan_body, headers={
            **headers, "Authorization": "Bearer " +
            jwt_for("foreign-tenant-jti-3210", role="tenant_owner"),
        },
    ).status_code == 403
    assert http.post(
        scan_path, json={**scan_body, "limit": True}, headers=headers,
    ).status_code == 422
    read = http.post(scan_path, json=scan_body, headers=headers)
    assert read.status_code == 200
    assert read.json()["created"] == 0
    assert read.json()["automated_dispatch_enabled"] is False

    # A synthetic persisted alert can be reviewed with an independent
    # step-upped FM identity without touching providers or tenant billing.
    event_id = "a" * 64
    with sessions.begin() as db:
        db.add(AIFinOpsAlertOutboxRecord(
            event_id=event_id, tenant_id="tenant-a", unit_id="unit-a",
            request_id="request-a", policy_revision=1,
            reasons_json='["provider_cost_unverified"]',
            known_cost_subtotal="0", currency=None, unknown_attempts=1,
            observed_attempts=1, status="pending",
            created_at=datetime.now(UTC), reviewed_at=None,
        ))
    review_path = "/internal/v1/command/ai/finops/alert-review"
    review_body = {
        "event_id": event_id, "tenant_id": "tenant-a", "unit_id": "unit-a",
    }
    assert http.post(review_path, json=review_body).status_code == 401
    review_headers = {
        **headers, "Authorization": "Bearer " +
        jwt_for("synthetic-review-jti-123456789"),
    }
    assert http.post(
        review_path, json={"event_id": "invalid"}, headers=review_headers,
    ).status_code == 422
    assert http.post(
        review_path,
        json={**review_body, "tenant_id": "foreign"},
        headers=review_headers,
    ).status_code == 409
    assert http.post(
        review_path,
        json={**review_body, "unit_id": "foreign"},
        headers=review_headers,
    ).status_code == 409
    assert http.post(
        review_path, json=review_body, headers=review_headers,
    ).status_code == 204
    with sessions() as db:
        row = db.get(AIFinOpsAlertOutboxRecord, event_id)
        assert row.status == "reviewed" and row.reviewed_at is not None

    # F3 regression: page 0 import must not shift the records on later pages.
    # Feed is mocked locally; no supplier or credential is contacted.
    from core import ai_finops_policy_api as finops_api
    from core.ai_provider_billing_export import ProviderExportPolicy, ProviderExportRecord
    from core.ai_usage_ledger import AIUsageRecord

    observed_at = datetime.now(UTC)
    with sessions.begin() as db:
        for index in range(3):
            db.add(AIUsageRecord(
                event_id=f"feed-event-{index}", attempt_id=f"feed-attempt-{index}",
                tenant_id="tenant-a", unit_id="unit-a", request_id=f"feed-req-{index}",
                correlation_id=f"feed-corr-{index}", capability="text",
                provider="provider-a", model="model-a", route_reason="primary",
                fallback_used=False, fallback_reason=None,
                input_tokens=12, output_tokens=5, cached_tokens=None,
                latency_ms=4, outcome="success", cost_decimal="0.004",
                currency="USD", cost_origin="estimated",
                price_snapshot_id="price-a", event_time=observed_at,
            ))
    seen_attempts = []
    monkeypatch.setattr(finops_api, "configured_feed", lambda _provider, _account: object())

    def provider_report(*, config, tenant_id, unit_id, attempts):
        del config
        seen_attempts.extend(row["attempt_id"] for row in attempts)
        return ProviderExportPolicy(
            provider="provider-a", adapter="openai_compatible",
            account_ref="fm-account",
        ), tuple(ProviderExportRecord(
            provider="provider-a", model=row["model"],
            tenant_id=tenant_id, unit_id=unit_id,
            request_id=row["request_id"], attempt_id=row["attempt_id"],
            account_ref="fm-account", source_ref="report-" + row["attempt_id"],
            observed_at=observed_at,
            usage={"prompt_tokens": 12, "completion_tokens": 5},
            cost_usd="0.004",
        ) for row in attempts)

    monkeypatch.setattr(finops_api, "fetch_observations", provider_report)
    sync_path = "/internal/v1/command/ai/finops/provider-export/sync"
    sync_body = {
        "tenant_id": "tenant-a", "unit_id": "unit-a",
        "provider": "provider-a", "account_ref": "fm-account",
        "start_date": observed_at.date().isoformat(),
        "end_date": observed_at.date().isoformat(), "limit": 1,
    }
    for page in range(3):
        response = http.post(
            sync_path, json={**sync_body, "page": page}, headers={
                **headers, "Authorization": "Bearer " +
                jwt_for(f"feed-admin-jti-{page}-distinct"),
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["created"] == 1
        assert response.json()["quota_recovery_authorized"] is False
        assert response.json()["next_page"] == (page + 1 if page < 2 else None)
    assert seen_attempts == [
        "feed-attempt-0", "feed-attempt-1", "feed-attempt-2",
    ]
