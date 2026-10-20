"""Corporate-authenticated initial plan binding; no customer-side elevation."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.command_bridge_control_service import sign_command_control
from fm_assistant.db import (
    Base,
    PlanBindingAuditORM,
    PlanLimitORM,
    PlanVersionORM,
    TenantLicenseORM,
    TenantORM,
)
from fm_assistant.plan_license_binding import (
    BIND_PATH,
    GovernedPlanLicenseBinding,
    PlanLicenseBindingDenied,
)

KEY = "synthetic-command-license-signing-key-for-tests-12345"


@pytest.fixture
def binding(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'license-binding.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with sessions.begin() as db:
        db.add(TenantORM(
            tenant_id="tenant-a", display_name="A", slug="tenant-a",
            status="active", created_at=now, updated_at=now,
        ))
        db.add(TenantLicenseORM(
            tenant_id="tenant-a", plan_code="trial", plan_revision=None,
            status="trial", trial_started_at=now - timedelta(hours=1),
            trial_ends_at=now + timedelta(days=10),
            period_started_at=None, period_ends_at=None,
            created_at=now, updated_at=now,
        ))
        db.add(PlanVersionORM(
            plan_code="PLAN_FULL", revision=1, label="Acesso integral",
            status="published", created_at=now,
        ))
        for metric in ("ai.requests", "ai.total_tokens"):
            db.add(PlanLimitORM(
                plan_code="PLAN_FULL", revision=1, resource=metric,
                scope="tenant", limit_units=500,
                window_seconds=86400,
            ))
    service = GovernedPlanLicenseBinding(
        sessions=sessions, signing_key=KEY, key_id="fm-key",
        trusted_organization="fm-corporate",
    )
    yield service, sessions
    engine.dispose()


def payload(**overrides):
    out = {
        "product_code": "VENDEATENDEIA",
        "organization_id": "fm-corporate", "actor_user_id": "fm-owner",
        "approved_at": int(datetime.now(UTC).timestamp()),
        "tenant_id": "tenant-a", "plan_code": "PLAN_FULL",
        "plan_revision": 1,
    }
    out.update(overrides)
    return out


def signed(body_data, *, nonce=None):
    raw = json.dumps(body_data, sort_keys=True, separators=(",", ":")).encode()
    ts = str(int(datetime.now(UTC).timestamp()))
    nonce = nonce or ("nonce-" + uuid4().hex)
    signature = sign_command_control(
        key=KEY, key_id="fm-key", timestamp=ts,
        nonce=nonce, body=raw, path=BIND_PATH,
    )
    return {
        "headers": {
            "key_id": "fm-key", "timestamp": ts,
            "nonce": nonce, "signature": signature,
        },
        "raw_body": raw,
        **body_data,
    }


def test_binding_links_existing_license_without_extending_period(binding):
    service, sessions = binding
    with sessions() as db:
        before = db.get(TenantLicenseORM, "tenant-a").trial_ends_at
    assert service.bind(**signed(payload())) == "bound"
    assert service.bind(**signed(payload())) == "already_bound"
    with sessions() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        assert (license_row.plan_code, license_row.plan_revision) == ("PLAN_FULL", 1)
        assert license_row.trial_ends_at == before
        assert license_row.status == "trial"
        rows = db.scalars(select(PlanBindingAuditORM)).all()
        assert len(rows) == 1
        assert rows[0].actor_id == "fm-owner"


def test_replay_forgery_and_other_product_denied(binding):
    service, sessions = binding
    original = signed(payload())
    assert service.bind(**original) == "bound"
    with pytest.raises(PlanLicenseBindingDenied):
        service.bind(**original)
    changed = signed(payload())
    changed["plan_revision"] = 2
    with pytest.raises(PlanLicenseBindingDenied):
        service.bind(**changed)
    with pytest.raises(PlanLicenseBindingDenied):
        service.bind(**signed(payload(product_code="KORDENA")))
    with pytest.raises(PlanLicenseBindingDenied):
        service.bind(**signed(payload(organization_id="foreign")))
    with sessions() as db:
        assert len(db.scalars(select(PlanBindingAuditORM)).all()) == 1


def test_different_revision_requires_separate_upgrade_workflow(binding):
    service, sessions = binding
    assert service.bind(**signed(payload())) == "bound"
    with sessions.begin() as db:
        db.add(PlanVersionORM(
            plan_code="PLAN_FULL", revision=2, label="Nova franquia",
            status="published", created_at=datetime.now(UTC),
        ))
        for metric in ("ai.requests", "ai.total_tokens"):
            db.add(PlanLimitORM(
                plan_code="PLAN_FULL", revision=2,
                resource=metric, scope="tenant", limit_units=1000,
                window_seconds=86400,
            ))
    with pytest.raises(PlanLicenseBindingDenied, match="transition_required"):
        service.bind(**signed(payload(plan_revision=2)))


def test_revoked_trial_or_missing_tenant_cannot_bind(binding):
    service, sessions = binding
    with pytest.raises(PlanLicenseBindingDenied):
        service.bind(**signed(payload(tenant_id="foreign")))
    with sessions.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.trial_ends_at = datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(PlanLicenseBindingDenied):
        service.bind(**signed(payload()))


def test_signed_binding_status_reports_persisted_match_without_reissuing_license(binding):
    from fm_assistant.plan_license_binding import STATUS_PATH

    service, sessions = binding
    req = payload()
    raw = json.dumps(req, sort_keys=True, separators=(",", ":")).encode()
    nonce = uuid4().hex
    ts = str(int(datetime.now(UTC).timestamp()))
    headers = {
        "key_id": "fm-key", "timestamp": ts, "nonce": nonce,
        "signature": sign_command_control(
            key=KEY, key_id="fm-key", timestamp=ts, nonce=nonce,
            body=raw, path=BIND_PATH,
        ),
    }
    assert service.bind(headers=headers, raw_body=raw, **req) == "bound"
    status_body = {
        k: req[k] for k in (
            "product_code", "organization_id", "tenant_id",
            "plan_code", "plan_revision",
        )
    }
    status_body["operation_nonce"] = nonce
    status_raw = json.dumps(status_body, sort_keys=True, separators=(",", ":")).encode()
    status_nonce = uuid4().hex
    status_headers = {
        "key_id": "fm-key", "timestamp": ts, "nonce": status_nonce,
        "signature": sign_command_control(
            key=KEY, key_id="fm-key", timestamp=ts,
            nonce=status_nonce, body=status_raw, path=STATUS_PATH,
        ),
    }
    assert service.binding_status(
        headers=status_headers, raw_body=status_raw, **status_body,
    ) == "bound_confirmed"
    with pytest.raises(PlanLicenseBindingDenied):
        service.binding_status(
            headers=status_headers, raw_body=status_raw, **status_body,
        )
    unknown = dict(status_body, plan_revision=2)
    missing_raw = json.dumps(unknown, sort_keys=True, separators=(",", ":")).encode()
    missing_nonce = uuid4().hex
    missing_headers = {
        "key_id": "fm-key", "timestamp": ts, "nonce": missing_nonce,
        "signature": sign_command_control(
            key=KEY, key_id="fm-key", timestamp=ts,
            nonce=missing_nonce, body=missing_raw, path=STATUS_PATH,
        ),
    }
    assert service.binding_status(
        headers=missing_headers, raw_body=missing_raw, **unknown,
    ) == "not_confirmed"
    with sessions() as session:
        events = session.scalars(select(PlanBindingAuditORM)).all()
        assert len(events) == 1


def test_binding_status_refuses_unsigned_foreign_scope(binding):
    from fm_assistant.plan_license_binding import STATUS_PATH

    service, _ = binding
    scope = {
        "product_code": "VENDEATENDEIA",
        "organization_id": "fm-corporate", "tenant_id": "tenant-a",
        "plan_code": "PLAN_FULL", "plan_revision": 1,
        "operation_nonce": uuid4().hex,
    }
    raw = json.dumps(scope).encode()
    ts = str(int(datetime.now(UTC).timestamp()))
    headers = {
        "key_id": "fm-key", "timestamp": ts, "nonce": uuid4().hex,
        "signature": "0" * 64,
    }
    with pytest.raises(PlanLicenseBindingDenied):
        service.binding_status(headers=headers, raw_body=raw, **scope)
    assert STATUS_PATH.endswith("/binding-status")
