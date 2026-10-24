"""Offline corporate security-hold coverage; no billing side effects."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.command_bridge_control_service import sign_command_control
from fm_assistant.db import Base, LicenseSecurityHoldAuditORM, TenantLicenseORM, TenantORM
from fm_assistant.license_security_hold import (
    PATH,
    LicenseSecurityHoldDenied,
    SignedLicenseSecurityHold,
)

KEY = "synthetic-fm-license-security-test-key-32-characters"


@pytest.fixture()
def subject(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path / 'license-hold.db'}")
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine,expire_on_commit=False)
    now=datetime.now(UTC)
    with sessions.begin() as db:
        db.add(TenantORM(
            tenant_id="t1",slug="tenant1",display_name="Test",status="active",
            created_at=now,updated_at=now,
        ))
        db.add(TenantLicenseORM(
            tenant_id="t1",plan_code="PLAN",plan_revision=1,
            status="active",trial_started_at=None,trial_ends_at=None,
            period_started_at=now,period_ends_at=now+timedelta(days=2),
            created_at=now,updated_at=now,
        ))
    service=SignedLicenseSecurityHold(
        sessions=sessions,signing_key=KEY,key_id="fm-key",
        trusted_organization="fm-corporate",
    )
    yield service,sessions
    engine.dispose()


def message(sessions,**changes):
    with sessions() as db:
        deadline=db.get(TenantLicenseORM,"t1").period_ends_at
    if deadline.tzinfo is None:
        deadline=deadline.replace(tzinfo=UTC)
    now=str(int(datetime.now(UTC).timestamp()))
    data={
        "product_code":"VENDEATENDEIA","organization_id":"fm-corporate",
        "tenant_id":"t1","actor_user_id":"fm-owner",
        "command_request_id":"hold-"+uuid4().hex,
        "approved_at":int(now),"step_up_at":int(now),
        "plan_code":"PLAN","plan_revision":1,
        "expected_valid_until":int(deadline.timestamp()),
        "reason":"security_hold",
    }
    data.update(changes)
    body=json.dumps(data,sort_keys=True,separators=(",",":")).encode()
    nonce="nonce-"+uuid4().hex
    auth={
        "key_id":"fm-key","timestamp":now,"nonce":nonce,
        "signature":sign_command_control(
            key=KEY,key_id="fm-key",timestamp=now,nonce=nonce,body=body,path=PATH,
        ),
    }
    return {"raw_body":body,"headers":auth,**data}


def test_signed_hold_is_atomic_and_replay_denied(subject):
    service,sessions=subject
    request=message(sessions)
    assert service.suspend(**request)=="suspended"
    with sessions() as db:
        assert db.get(TenantLicenseORM,"t1").status=="suspended"
        rows=db.scalars(select(LicenseSecurityHoldAuditORM)).all()
        assert len(rows)==1 and rows[0].old_status=="active"
    with pytest.raises(LicenseSecurityHoldDenied):
        service.suspend(**request)


def test_cross_tenant_stale_and_unsigned_requests_denied(subject):
    service,sessions=subject
    for changes in (
        {"tenant_id":"other"},
        {"organization_id":"other"},
        {"plan_revision":2},
        {"reason":"refund"},
        {"step_up_at":int(datetime.now(UTC).timestamp())-600},
        {"expected_valid_until":int(datetime.now(UTC).timestamp())+500},
    ):
        with pytest.raises(LicenseSecurityHoldDenied):
            service.suspend(**message(sessions,**changes))
    request=message(sessions)
    request["headers"]["signature"]="0"*64
    with pytest.raises(LicenseSecurityHoldDenied):
        service.suspend(**request)
    with sessions() as db:
        assert db.get(TenantLicenseORM,"t1").status=="active"
        assert db.scalars(select(LicenseSecurityHoldAuditORM)).all()==[]
