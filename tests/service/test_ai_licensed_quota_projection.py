"""Assistant-signed license snapshot → exact Core quota projection/reservation."""
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase
from core.ai_licensed_quota_projection import (
    ExpectedLicensedScope,
    reserve_licensed_ai_attempt,
)
from core.ai_quota_store import QuotaDenied, QuotaReservations

KEY = b"internal-assistant-core-licensed-quota-test-key-32"
NOW = datetime(2026, 10, 19, 21, tzinfo=UTC)
SCOPE = ExpectedLicensedScope(
    tenant_id="tenant-a", unit_id="unit-a",
    capability="ai.text", challenge="nonce12345678901234567890123",
)


def _signed(*, expires=None, revision=5, limit=1000, tenant="tenant-a"):
    body = {
        "tenant_id": tenant, "unit_id": "unit-a",
        "capability": "ai.text", "challenge": SCOPE.challenge,
        "plan_code": "standard", "revision": revision,
        "expires_at": int((expires or (NOW + timedelta(seconds=25))).timestamp()),
        "licensed_until": int((NOW + timedelta(days=10)).timestamp()),
        "input_bound": 250, "output_bound": 150,
        "scopes": [["ai.requests", "tenant"], ["ai.total_tokens", "tenant"]],
        "grants": [
            ["ai.requests", "tenant", 20, 3600],
            ["ai.total_tokens", "tenant", limit, 3600],
        ],
    }
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    tag = hmac.new(
        KEY, b"/internal/v1/assistant/core-plan-grant\n" + payload,
        hashlib.sha256,
    ).hexdigest()
    return payload, tag


@pytest.fixture
def ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'license-core.sqlite'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield QuotaReservations(sessions)
    finally:
        engine.dispose()


def _reserve(ledger, payload, signature, *, request="request-1"):
    return reserve_licensed_ai_attempt(
        payload=payload, signature=signature, key=KEY,
        expected=SCOPE, ledger=ledger, at=NOW,
        request_id=request, input_budget=250, output_budget=150,
    )


def test_signed_plan_projects_and_atomically_reserves_core_quota(ledger):
    payload, sig = _signed()
    _reserve(ledger, payload, sig)
    snapshot = ledger.usage_snapshot(
        tenant_id="tenant-a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert snapshot.limit_units == 1000
    assert snapshot.reserved_units == 400
    assert snapshot.remaining_units == 600
    with pytest.raises(QuotaDenied):
        _reserve(ledger, payload, sig)  # never authorize same request twice


def test_expired_or_foreign_or_tampered_grant_cannot_reserve(ledger):
    expired, tag = _signed(expires=NOW - timedelta(seconds=1))
    with pytest.raises(QuotaDenied):
        _reserve(ledger, expired, tag)
    foreign, tag = _signed(tenant="tenant-b")
    with pytest.raises(QuotaDenied):
        _reserve(ledger, foreign, tag)
    genuine, tag = _signed()
    with pytest.raises(QuotaDenied):
        _reserve(ledger, genuine.replace(b"1000", b"9999"), tag)


def test_revision_downgrade_denied_after_new_projection(ledger):
    current, current_tag = _signed(revision=6)
    _reserve(ledger, current, current_tag, request="request-6")
    stale, stale_tag = _signed(revision=5)
    with pytest.raises(QuotaDenied, match="projection_stale"):
        _reserve(ledger, stale, stale_tag, request="request-5")


def test_failed_reservation_does_not_consume_quota(ledger):
    tiny, tag = _signed(limit=100)
    with pytest.raises(QuotaDenied):
        _reserve(ledger, tiny, tag)
    snapshot = ledger.usage_snapshot(
        tenant_id="tenant-a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert snapshot.consumed_units == 0
    assert snapshot.reserved_units == 0
