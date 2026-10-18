"""Signed corporate plan revision projection, isolated from production."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.command_bridge_control_service import sign_command_control
from fm_assistant.db import Base, PlanLimitORM, PlanSyncNonceORM, PlanVersionORM
from fm_assistant.plan_sync_service import (
    PATH,
    CommandPlanProjectionService,
    PlanSyncDenied,
)

KEY = "synthetic-plan-key-0123456789-abcdefghijklmnopqrstuvwxyz"


@pytest.fixture()
def catalog(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'projected-plans.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    service = CommandPlanProjectionService(
        sessions=sessions, key_id="fm-command",
        signing_key=KEY, trusted_organization="fm-org",
    )
    yield service, sessions
    engine.dispose()


def document(*, amount=500000, revision=1):
    return {
        "product_code": "VENDEATENDEIA",
        "organization_id": "fm-org",
        "actor_user_id": "fm-owner",
        "step_up_at": int(datetime.now(UTC).timestamp()),
        "plan_code": "VENDE_TEST", "revision": revision,
        "label": "Todos os recursos, franquia controlada",
        "allowances": [
            {"resource": "ai.requests", "scope": "tenant",
             "limitUnits": 1000, "windowSeconds": 86400},
            {"resource": "ai.total_tokens", "scope": "tenant",
             "limitUnits": amount, "windowSeconds": 86400},
        ],
    }


def signed(payload, *, nonce=None):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    nonce = nonce or ("nonce-" + uuid4().hex)
    signature = sign_command_control(
        key=KEY, key_id="fm-command", timestamp=timestamp,
        nonce=nonce, body=body, path=PATH,
    )
    args = dict(
        raw_body=body,
        headers={"key_id": "fm-command", "timestamp": timestamp,
                 "nonce": nonce, "signature": signature},
        **payload,
    )
    args["allowances"] = tuple(payload["allowances"])
    return args


def test_imports_published_plan_without_price_or_feature_gating(catalog):
    service, sessions = catalog
    doc = document()
    assert service.apply(**signed(doc)) == "projected"
    with sessions() as db:
        v = db.get(PlanVersionORM, ("VENDE_TEST", 1))
        caps = db.scalars(select(PlanLimitORM)).all()
        assert v is not None and v.status == "published"
        assert len(caps) == 2
        assert {i.resource for i in caps} == {"ai.requests", "ai.total_tokens"}
    assert service.apply(**signed(doc)) == "already_projected"
    with sessions() as db:
        assert len(db.scalars(select(PlanSyncNonceORM)).all()) == 2


def test_conflicting_version_and_nonce_replay_are_denied(catalog):
    service, sessions = catalog
    doc = document()
    original = signed(doc)
    assert service.apply(**original) == "projected"
    with pytest.raises(PlanSyncDenied):
        service.apply(**original)
    with pytest.raises(PlanSyncDenied):
        service.apply(**signed(document(amount=999)))
    with sessions() as db:
        assert db.get(PlanLimitORM, ("VENDE_TEST", 1, "ai.total_tokens")).limit_units == 500000


def test_other_product_tenant_feature_switch_and_tampering_denied(catalog):
    service, sessions = catalog
    for field, value in (
        ("organization_id", "foreign"),
        ("product_code", "KORDENA"),
    ):
        doc = document()
        doc[field] = value
        with pytest.raises(PlanSyncDenied):
            service.apply(**signed(doc))
    doc = document()
    doc["allowances"][0]["enabled"] = False
    with pytest.raises(PlanSyncDenied):
        service.apply(**signed(doc))
    doc = document()
    request = signed(doc)
    request["plan_code"] = "ELEVATED"
    with pytest.raises(PlanSyncDenied):
        service.apply(**request)
    with sessions() as db:
        assert db.scalars(select(PlanVersionORM)).all() == []


def test_missing_token_quota_never_becomes_unlimited(catalog):
    service, _ = catalog
    doc = document()
    doc["allowances"].pop()
    with pytest.raises(PlanSyncDenied):
        service.apply(**signed(doc))
