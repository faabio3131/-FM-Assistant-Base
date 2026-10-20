"""Corporate-signed QR policy projection: no tenant writes or stale QR relaxation."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.command_bridge_control_service import sign_command_control
from fm_assistant.db import Base, PlanSyncNonceORM, WhatsAppQRDisplayPolicyORM
from fm_assistant.qr_onboarding_page import render_qr_page
from fm_assistant.qr_policy_sync import (
    PATH,
    CommandQrDisplayPolicyService,
    QrDisplayPolicyDenied,
)

SIGNING_KEY = "synthetic-corporate-qr-sync-key-of-sufficient-entropy"


@pytest.fixture()
def policy(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'qr-policy.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    sync = CommandQrDisplayPolicyService(
        sessions=sessions, key_id="fm-qr-key",
        signing_key=SIGNING_KEY, trusted_organization="fm-org",
    )
    yield sync, sessions
    engine.dispose()


def policy_doc(*, revision=1, display_seconds=45):
    return {
        "product_code": "VENDEATENDEIA",
        "organization_id": "fm-org",
        "actor_user_id": "fm-owner",
        "approved_at": int(datetime.now(UTC).timestamp()),
        "revision": revision,
        "display_seconds": display_seconds,
    }


def signed(doc, *, nonce=None):
    raw = json.dumps(doc, separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    nonce = nonce or ("nonce-" + uuid4().hex)
    return {
        **doc,
        "raw_body": raw,
        "headers": {
            "key_id": "fm-qr-key", "timestamp": timestamp, "nonce": nonce,
            "signature": sign_command_control(
                key=SIGNING_KEY, key_id="fm-qr-key",
                timestamp=timestamp, nonce=nonce, body=raw, path=PATH,
            ),
        },
    }


def test_default_qr_cap_and_monotonic_fm_projection(policy):
    service, sessions = policy
    assert service.read() == (45, 0)
    assert service.apply(**signed(policy_doc(revision=2, display_seconds=20))) == "projected"
    assert service.read() == (20, 2)
    assert service.apply(**signed(policy_doc(revision=2, display_seconds=20))) == "already_projected"
    assert service.apply(**signed(policy_doc(revision=5, display_seconds=60))) == "projected"
    assert service.read() == (60, 5)
    with sessions() as db:
        row = db.get(WhatsAppQRDisplayPolicyORM, "VENDEATENDEIA")
        assert row.organization_id == "fm-org"
        assert len(db.scalars(select(PlanSyncNonceORM)).all()) == 3


def test_replay_stale_revision_and_conflict_never_relax_display(policy):
    service, _ = policy
    first = signed(policy_doc(display_seconds=15))
    assert service.apply(**first) == "projected"
    with pytest.raises(QrDisplayPolicyDenied):
        service.apply(**first)
    with pytest.raises(QrDisplayPolicyDenied):
        service.apply(**signed(policy_doc(revision=1, display_seconds=120)))
    assert service.apply(**signed(policy_doc(revision=4, display_seconds=30))) == "projected"
    with pytest.raises(QrDisplayPolicyDenied):
        service.apply(**signed(policy_doc(revision=2, display_seconds=120)))
    assert service.read() == (30, 4)


def test_tampering_cross_product_bad_signature_and_range_fail_closed(policy):
    service, sessions = policy
    base = policy_doc()
    for field, value in (
        ("organization_id", "other-org"),
        ("product_code", "IRON"),
        ("display_seconds", 14),
        ("display_seconds", 121),
        ("display_seconds", True),
        ("revision", True),
        ("actor_user_id", "not allowed whitespace"),
    ):
        doc = {**base, field: value}
        with pytest.raises(QrDisplayPolicyDenied):
            service.apply(**signed(doc))
    tampered = signed(base)
    tampered["display_seconds"] = 120
    with pytest.raises(QrDisplayPolicyDenied):
        service.apply(**tampered)
    wrong_path = signed(base)
    wrong_path["headers"]["signature"] = sign_command_control(
        key=SIGNING_KEY, key_id="fm-qr-key",
        timestamp=wrong_path["headers"]["timestamp"],
        nonce=wrong_path["headers"]["nonce"],
        body=wrong_path["raw_body"], path="/internal/v1/command/assistant-plans/project",
    )
    with pytest.raises(QrDisplayPolicyDenied):
        service.apply(**wrong_path)
    assert service.read() == (45, 0)
    with sessions() as db:
        assert db.scalars(select(PlanSyncNonceORM)).all() == []


def test_panel_uses_dynamic_cap_and_never_extends_existing_qr_deadline():
    page, csp = render_qr_page()
    assert "setDisplayCap(current.qr_display_seconds)" in page
    assert "setDisplayCap(latest.qr_display_seconds)" in page
    assert "shownAt+QR_DISPLAY_CAP_MS-Date.now()" in page
    assert "setTimeout(expire,remaining)" in page
    assert "QR_DISPLAY_CAP_MS=45000" in page
    assert "frame-ancestors 'none'" in csp
