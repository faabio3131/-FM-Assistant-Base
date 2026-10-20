"""Recovery receipts map to Core policies, not an Assistant-side ledger."""
from decimal import Decimal

import pytest

from core.ai_quota_store import QuotaDenied
from core.ai_verified_usage_receipt import (
    VerifiedProviderUsageReceipt,
    recovery_bundle_from_verified_receipt,
)


def _receipt(*, no_charge=False, tokens=200, cost="0.02", tenant="tenant-A"):
    return VerifiedProviderUsageReceipt(
        provider="gemini", model="gemini-model",
        request_id="request-1", tenant_id=tenant, unit_id="unit-1",
        input_tokens=0 if no_charge else tokens,
        output_tokens=0 if no_charge or tokens == 0 else 50,
        provider_cost_usd=Decimal(cost),
        evidence_digest="a" * 64, no_charge=no_charge,
    )


def test_verified_provider_token_usage_maps_to_core_authoritative_quotas():
    requirements = recovery_bundle_from_verified_receipt(
        _receipt(), request_policy_revision=3, tokens_policy_revision=3,
    )
    assert [(x.capability, x.units) for x in requirements] == [
        ("ai.requests", 1), ("ai.total_tokens", 250),
    ]
    assert all(x.tenant_id == "tenant-A" and x.unit_id == "__tenant__"
               and x.policy_revision == 3 for x in requirements)


def test_verified_no_charge_has_zero_bundle_but_is_not_inferred_from_timeout():
    requirements = recovery_bundle_from_verified_receipt(
        _receipt(no_charge=True, tokens=0, cost="0"),
        request_policy_revision=3, tokens_policy_revision=3,
    )
    assert all(x.units == 0 for x in requirements)
    with pytest.raises(QuotaDenied):
        recovery_bundle_from_verified_receipt(
            _receipt(tokens=0), request_policy_revision=3,
            tokens_policy_revision=3,
        )


@pytest.mark.parametrize("field,value", [
    ("input_tokens", -1),
    ("input_tokens", True),
    ("output_tokens", 0.5),
    ("provider_cost_usd", Decimal("NaN")),
    ("evidence_digest", "forged"),
    ("tenant_id", ""),
])
def test_malformed_receipt_never_generates_recovery_charge(field, value):
    args = {
        "provider": "gemini", "model": "m", "request_id": "r",
        "tenant_id": "tenant-A", "unit_id": "unit-1", "input_tokens": 1,
        "output_tokens": 2, "provider_cost_usd": Decimal("0.1"),
        "evidence_digest": "c" * 64, "no_charge": False,
    }
    args[field] = value
    with pytest.raises(QuotaDenied):
        VerifiedProviderUsageReceipt(**args)


def test_recovery_scope_and_revision_cannot_be_forged():
    with pytest.raises(QuotaDenied):
        recovery_bundle_from_verified_receipt(
            _receipt(), request_policy_revision=True,
            tokens_policy_revision=2,
        )
    with pytest.raises(QuotaDenied):
        recovery_bundle_from_verified_receipt(
            _receipt(), request_policy_revision=2,
            tokens_policy_revision=2, request_scope="other-unit",
        )


def test_license_projection_reservation_and_verified_recovery_use_same_core_ledger(tmp_path):
    """Synthetic Command policy → Assistant scope → Core reserve/reconcile."""
    from datetime import UTC, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.ai_command_authority import VerifiedCommandAdmin
    from core.ai_control_plane import ControlPlaneBase
    from core.ai_quota_store import QuotaRequirement, QuotaReservations

    now = datetime(2026, 10, 19, 12, tzinfo=UTC)
    engine = create_engine(f"sqlite:///{tmp_path / 'signed-plan-usage.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    ledger = QuotaReservations(sessions)
    try:
        ledger.project_signed_grants(
            tenant_id="tenant-A", unit_id="unit-1", revision=5,
            grants=(("ai.requests", "tenant", 50, 3600),
                    ("ai.total_tokens", "tenant", 3000, 3600)),
        )
        reserved = (
            QuotaRequirement(
                tenant_id="tenant-A", unit_id="__tenant__",
                capability="ai.requests", units=1, policy_revision=5,
            ),
            QuotaRequirement(
                tenant_id="tenant-A", unit_id="__tenant__",
                capability="ai.total_tokens", units=450, policy_revision=5,
            ),
        )
        ledger.reserve_bundle(
            needs=reserved, request_id="request-1", at=now,
        )
        before = ledger.usage_snapshot(
            tenant_id="tenant-A", unit_id="__tenant__",
            capability="ai.total_tokens", at=now,
        )
        assert before.reserved_units == 450
        human = VerifiedCommandAdmin(
            user_id="human", session_id="session",
            token_id="command-admin-jti-license-123",
            issued_at=int(now.timestamp()) - 5,
            expires_at=int(now.timestamp()) + 60,
            step_up_at=int(now.timestamp()) - 5,
            permissions=frozenset({"core.ai.admin.mutate"}),
        )
        ledger.reconcile_verified_provider_receipt(
            receipt=_receipt(tokens=200, cost="0.02"),
            request_policy_revision=5, tokens_policy_revision=5,
            principal=human, at=now,
        )
        after = ledger.usage_snapshot(
            tenant_id="tenant-A", unit_id="__tenant__",
            capability="ai.total_tokens", at=now,
        )
        assert after.reserved_units == 0
        assert after.consumed_units == 250
        assert after.remaining_units == 2750
        with pytest.raises(QuotaDenied):
            ledger.reconcile_verified_provider_receipt(
                receipt=_receipt(tokens=200, cost="0.02"),
                request_policy_revision=5, tokens_policy_revision=5,
                principal=human, at=now,
            )
    finally:
        engine.dispose()
