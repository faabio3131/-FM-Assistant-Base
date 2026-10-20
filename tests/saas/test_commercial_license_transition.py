"""Synthetic FM commercial lifecycle HMAC → SQL license transitions.

No gateway credentials, production database, invoice mutation or network.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.command_bridge_control_service import sign_command_control
from fm_assistant.commercial_license_transition import (
    PATH, CommercialLicenseTransitionDenied, SignedCommercialLicenseTransition,
)
from fm_assistant.db import (
    Base, CommercialLicenseTransitionAuditORM, PlanLimitORM, PlanVersionORM,
    TenantLicenseORM, TenantORM,
)
from fm_assistant.plan_limits import PlanLimitDenied, PlanLimitResolver

KEY = "synthetic-FM-commercial-transition-HMAC-key-of-adequate-length"


@pytest.fixture()
def commercial(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path / 'commercial.db'}")
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine, expire_on_commit=False)
    now=datetime.now(UTC).replace(microsecond=0)
    with sessions.begin() as db:
        db.add(TenantORM(
            tenant_id="tenant-one",slug="commercial-a",display_name="Test",
            status="active",created_at=now,updated_at=now,
        ))
        db.add(TenantLicenseORM(
            tenant_id="tenant-one",plan_code="BASE",plan_revision=1,
            status="active",trial_started_at=None,trial_ends_at=None,
            period_started_at=now-timedelta(days=1),
            period_ends_at=now+timedelta(days=2),
            created_at=now,updated_at=now,
        ))
        for code in ("BASE", "PLUS"):
            db.add(PlanVersionORM(
                plan_code=code,revision=1,label=code,
                status="published",created_at=now,
            ))
            for metric in ("ai.requests","ai.total_tokens"):
                db.add(PlanLimitORM(
                    plan_code=code,revision=1,resource=metric,
                    scope="tenant",limit_units=100,window_seconds=86400,
                ))
    service=SignedCommercialLicenseTransition(
        sessions=sessions,signing_key=KEY,key_id="fm-commercial-key",
        trusted_organization="fm-company",
    )
    yield service,sessions
    engine.dispose()


def signed(sessions,action,**overrides):
    with sessions() as db:
        row=db.get(TenantLicenseORM,"tenant-one")
        expiry=row.period_ends_at
        old=row.status
        code=row.plan_code
        revision=row.plan_revision
    if expiry.tzinfo is None:
        expiry=expiry.replace(tzinfo=UTC)
    stamp=int(datetime.now(UTC).timestamp())
    data={
        "product_code":"VENDEATENDEIA","organization_id":"fm-company",
        "tenant_id":"tenant-one","actor_user_id":"fm-human",
        "command_request_id":"operation-"+uuid4().hex,
        "approved_at":stamp,"action":action,
        "expected_status":old,
        "expected_plan_code":code,"expected_plan_revision":revision,
        "expected_valid_until":int(expiry.timestamp()),
        "target_plan_code":code,"target_plan_revision":revision,
        "target_valid_until":int(expiry.timestamp()),
        "effective_at":stamp,
        "verified_payment_ref":"provider-reconciled-"+uuid4().hex
            if action in {
                "REACTIVATE_VERIFIED","RENEW_VERIFIED","APPLY_UPGRADE","APPLY_DOWNGRADE",
            } else "none",
    }
    data.update(overrides)
    raw=json.dumps(data,separators=(",",":"),sort_keys=True).encode()
    nonce="nonce-"+uuid4().hex
    ts=str(stamp)
    headers={
        "key_id":"fm-commercial-key","timestamp":ts,"nonce":nonce,
        "signature":sign_command_control(
            key=KEY,key_id="fm-commercial-key",timestamp=ts,
            nonce=nonce,body=raw,path=PATH,
        ),
    }
    return {"headers":headers,"raw_body":raw,**data}


def test_delinquency_is_not_security_hold_and_requires_exact_signed_cas(commercial):
    service,sessions=commercial
    request=signed(sessions,"SUSPEND_DELINQUENCY")
    assert service.apply(**request)=="suspended"
    with sessions() as db:
        assert db.get(TenantLicenseORM,"tenant-one").status=="suspended"
        audits=db.scalars(select(CommercialLicenseTransitionAuditORM)).all()
        assert len(audits)==1 and audits[0].action=="SUSPEND_DELINQUENCY"
    with pytest.raises(CommercialLicenseTransitionDenied):
        service.apply(**request)
    # Existing signed step-up security-hold endpoint has a distinct MAC domain.
    from fm_assistant.license_security_hold import PATH as SECURITY_PATH
    assert PATH != SECURITY_PATH
    with pytest.raises(CommercialLicenseTransitionDenied):
        service.apply(**signed(sessions,"SUSPEND_DELINQUENCY",expected_status="active"))


def test_paid_regularization_same_tenant_id_and_no_automatic_trial(commercial):
    service,sessions=commercial
    assert service.apply(**signed(sessions,"SUSPEND_DELINQUENCY"))=="suspended"
    with sessions() as db:
        current=db.get(TenantLicenseORM,"tenant-one").period_ends_at
    if current.tzinfo is None:
        current=current.replace(tzinfo=UTC)
    until=int((datetime.now(UTC)+timedelta(days=31)).timestamp())
    request=signed(sessions,"REACTIVATE_VERIFIED",target_valid_until=until)
    assert service.apply(**request)=="active"
    with sessions() as db:
        license_row=db.get(TenantLicenseORM,"tenant-one")
        assert license_row.status=="active"
        assert license_row.tenant_id=="tenant-one"
        assert int(license_row.period_ends_at.replace(tzinfo=UTC).timestamp())==until
        assert license_row.trial_ends_at is None
    with pytest.raises(CommercialLicenseTransitionDenied):
        service.apply(**request)
    assert int(current.timestamp())<until


def test_upgrade_requires_published_target_and_preserves_paid_deadline(commercial):
    service,sessions=commercial
    request=signed(sessions,"APPLY_UPGRADE",target_plan_code="PLUS")
    assert service.apply(**request)=="active"
    with sessions() as db:
        row=db.get(TenantLicenseORM,"tenant-one")
        assert row.plan_code=="PLUS" and row.plan_revision==1
        assert int(row.period_ends_at.replace(tzinfo=UTC).timestamp())==request["expected_valid_until"]


def test_renewal_rejects_fake_payment_and_never_accepts_same_cutoff(commercial):
    service,sessions=commercial
    valid=signed(sessions,"RENEW_VERIFIED",target_valid_until=
        int((datetime.now(UTC)+timedelta(days=33)).timestamp()))
    with pytest.raises(CommercialLicenseTransitionDenied):
        service.apply(**{**valid,"verified_payment_ref":"none"})
    with pytest.raises(CommercialLicenseTransitionDenied):
        service.apply(**signed(sessions,"RENEW_VERIFIED"))
    assert service.apply(**valid)=="active"


def test_replay_cross_tenant_fake_plan_bad_signature_and_clock_denied(commercial):
    service,sessions=commercial
    for mutation in (
        {"tenant_id":"foreign"},
        {"organization_id":"untrusted"},
        {"expected_plan_revision":2},
        {"target_plan_code":"UNPUBLISHED"},
        {"approved_at":int(datetime.now(UTC).timestamp())-301},
        {"expected_valid_until":1},
    ):
        with pytest.raises(CommercialLicenseTransitionDenied):
            service.apply(**signed(sessions,"APPLY_UPGRADE",**mutation))
    tampered=signed(sessions,"SUSPEND_DELINQUENCY")
    tampered["headers"]["signature"]="0"*64
    with pytest.raises(CommercialLicenseTransitionDenied):
        service.apply(**tampered)
    with sessions() as db:
        assert db.scalars(select(CommercialLicenseTransitionAuditORM)).all()==[]
        assert db.get(TenantLicenseORM,"tenant-one").status=="active"
