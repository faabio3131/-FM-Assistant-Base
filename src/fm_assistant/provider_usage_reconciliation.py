"""Fail-closed reconciliation of provider usage: no guessed tokens or refunds.

Provider billing/cost figures are internal FM information and must never be
confused with tenant-visible quotas (whose authority remains FM Core).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True, kw_only=True)
class ProviderUsage:
    provider: str
    model: str
    request_id: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    status: str

    def __post_init__(self) -> None:
        if (
            not all(isinstance(x, str) and 0 < len(x) <= 160
                    for x in (self.provider, self.model, self.request_id))
            or self.status not in {"confirmed", "uncertain"}
        ):
            raise ValueError("provider_usage_invalid")
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("provider_usage_invalid")
        if self.cost_usd is not None and (
            not isinstance(self.cost_usd, Decimal)
            or not self.cost_usd.is_finite() or self.cost_usd < 0
        ):
            raise ValueError("provider_usage_invalid")
        if self.status == "uncertain" and (
            self.input_tokens is not None or self.output_tokens is not None
            or self.cost_usd is not None
        ):
            raise ValueError("provider_usage_uncertain_requires_unknown_values")
        if self.status == "confirmed" and (
            self.input_tokens is None or self.output_tokens is None
        ):
            raise ValueError("provider_usage_confirmation_requires_known_tokens")

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


def from_trusted_core_receipt(receipt: dict, *, request_id: str) -> ProviderUsage:
    """Parse trusted Core result only. No fallback from text length or pricing."""
    if not isinstance(receipt, dict) or receipt.get("request_id") != request_id:
        raise ValueError("provider_usage_receipt_mismatch")
    if not all(
        isinstance(receipt.get(key), str) and receipt[key].strip()
        for key in ("provider", "model")
    ):
        raise ValueError("provider_usage_identity_invalid")
    state = receipt.get("usage_status")
    if state == "uncertain":
        if any(receipt.get(key) is not None for key in (
            "input_tokens", "output_tokens", "cost_usd",
        )):
            raise ValueError("provider_usage_uncertain_contradictory_evidence")
        return ProviderUsage(
            provider=receipt["provider"], model=receipt["model"],
            request_id=request_id, input_tokens=None, output_tokens=None,
            cost_usd=None, status="uncertain",
        )
    if state != "confirmed":
        raise ValueError("provider_usage_status_invalid")
    raw_cost = receipt.get("cost_usd")
    if raw_cost is not None and (type(raw_cost) is not str or not 1 <= len(raw_cost) <= 80):
        raise ValueError("provider_usage_cost_invalid")
    try:
        cost = Decimal(raw_cost) if raw_cost is not None else None
    except InvalidOperation as exc:
        raise ValueError("provider_usage_cost_invalid") from exc
    return ProviderUsage(
        provider=receipt["provider"], model=receipt["model"],
        request_id=request_id, input_tokens=receipt.get("input_tokens"),
        output_tokens=receipt.get("output_tokens"), cost_usd=cost,
        status="confirmed",
    )


def reconcile_usage(original: ProviderUsage, receipt: ProviderUsage) -> ProviderUsage:
    """Idempotent single-request state resolution, never double charge.

    Conflicting confirmed readings cannot be silently overwritten.
    """
    if (
        original.request_id != receipt.request_id
        or original.provider != receipt.provider
        or original.model != receipt.model
    ):
        raise ValueError("provider_usage_identity_mismatch")
    if original.status == "confirmed":
        if original != receipt:
            raise RuntimeError("provider_usage_conflicting_confirmation")
        return original
    return receipt if receipt.status == "confirmed" else original
