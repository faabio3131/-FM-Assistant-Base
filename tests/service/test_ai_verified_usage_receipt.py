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
        output_tokens=0 if no_charge else 50,
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
    args = dict(
        provider="gemini", model="m", request_id="r",
        tenant_id="tenant-A", unit_id="unit-1", input_tokens=1,
        output_tokens=2, provider_cost_usd=Decimal("0.1"),
        evidence_digest="c" * 64, no_charge=False,
    )
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
