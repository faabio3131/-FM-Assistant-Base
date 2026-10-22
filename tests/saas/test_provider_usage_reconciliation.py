"""FM-owned FinOps controls: no synthetic pricing, double charge or refund."""
from decimal import Decimal

import pytest

from fm_assistant.provider_usage_reconciliation import (
    ProviderUsage,
    from_trusted_core_receipt,
    reconcile_usage,
)


def test_unknown_cost_and_tokens_remain_unknown():
    unknown = from_trusted_core_receipt(
        {"request_id": "req-1", "usage_status": "uncertain",
         "provider": "gemini", "model": "gemini-model"},
        request_id="req-1",
    )
    assert unknown.total_tokens is None
    assert unknown.cost_usd is None
    assert unknown.status == "uncertain"


def test_only_confirmed_core_receipts_set_billable_usage():
    unknown = ProviderUsage(
        provider="gemini", model="model-1", request_id="req-1",
        input_tokens=None, output_tokens=None, cost_usd=None,
        status="uncertain",
    )
    confirmed = from_trusted_core_receipt(
        {"request_id": "req-1", "usage_status": "confirmed",
         "provider": "gemini", "model": "model-1",
         "input_tokens": 250, "output_tokens": 125,
         "cost_usd": "0.0025"},
        request_id="req-1",
    )
    assert confirmed.total_tokens == 375
    assert confirmed.cost_usd == Decimal("0.0025")
    assert reconcile_usage(unknown, confirmed) == confirmed
    assert reconcile_usage(confirmed, confirmed) == confirmed
    with pytest.raises(RuntimeError, match="provider_usage_conflicting_confirmation"):
        reconcile_usage(
            confirmed,
            ProviderUsage(
                provider="gemini", model="model-1", request_id="req-1",
                input_tokens=250, output_tokens=126,
                cost_usd=Decimal("0.0025"), status="confirmed",
            ),
        )


@pytest.mark.parametrize("bad", [
    {"request_id": "other", "usage_status": "confirmed",
     "provider": "a", "model": "b", "input_tokens": 1, "output_tokens": 2},
    {"request_id": "r", "usage_status": "confirmed",
     "provider": "a", "model": "b", "input_tokens": -1, "output_tokens": 2},
    {"request_id": "r", "usage_status": "confirmed",
     "provider": "a", "model": "b", "input_tokens": 1, "output_tokens": 2,
     "cost_usd": "NaN"},
    {"request_id": "r", "usage_status": "uncertain",
     "provider": "a", "model": ""},
])
def test_invalid_receipts_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        from_trusted_core_receipt(bad, request_id="r")


@pytest.mark.parametrize("bad", [
    {"usage_status": "confirmed", "input_tokens": None, "output_tokens": 2},
    {"usage_status": "confirmed", "input_tokens": 1, "output_tokens": None},
    {"usage_status": "confirmed", "input_tokens": 1, "output_tokens": 2,
     "cost_usd": 0.5},
    {"usage_status": "confirmed", "input_tokens": 1, "output_tokens": 2,
     "cost_usd": True},
    {"usage_status": "uncertain", "input_tokens": 1, "output_tokens": None},
    {"usage_status": "uncertain", "cost_usd": "0.00"},
])
def test_ambiguous_and_contradictory_provider_usage_fails_closed(bad):
    receipt = {"request_id": "req-a", "provider": "gemini", "model": "model-a", **bad}
    with pytest.raises(ValueError):
        from_trusted_core_receipt(receipt, request_id="req-a")


def test_confirmed_tokens_can_retain_unknown_cost_without_claiming_free_usage():
    reading = from_trusted_core_receipt({
        "request_id": "req-a", "provider": "gemini", "model": "model-a",
        "usage_status": "confirmed", "input_tokens": 40,
        "output_tokens": 12, "cost_usd": None,
    }, request_id="req-a")
    assert reading.total_tokens == 52
    assert reading.cost_usd is None
    assert reading.status == "confirmed"


def test_provider_or_request_switch_never_reconciles():
    old = ProviderUsage(
        provider="gemini", model="m", request_id="req",
        input_tokens=None, output_tokens=None, cost_usd=None,
        status="uncertain",
    )
    foreign = ProviderUsage(
        provider="openai", model="m", request_id="req",
        input_tokens=1, output_tokens=2, cost_usd=None,
        status="confirmed",
    )
    with pytest.raises(ValueError, match="provider_usage_identity_mismatch"):
        reconcile_usage(old, foreign)
