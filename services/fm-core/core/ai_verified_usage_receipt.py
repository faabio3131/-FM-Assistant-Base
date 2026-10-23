"""Provider usage evidence normalization for governed Core quota recovery.

This module accepts evidence ONLY after a separate trusted provider verification.
It does not authorize quota settlement, invent token charges, or grant an admin
identity. QuotaReservations.reconcile_ambiguous_bundle owns atomic settlement.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.ai_quota_store import QuotaDenied, QuotaRequirement


@dataclass(frozen=True, kw_only=True)
class VerifiedProviderUsageReceipt:
    provider: str
    model: str
    request_id: str
    tenant_id: str
    unit_id: str
    input_tokens: int
    output_tokens: int
    provider_cost_usd: Decimal | None
    evidence_digest: str
    # A verified provider no-charge attestation has a different evidence type.
    no_charge: bool = False

    def __post_init__(self) -> None:
        import re

        values = (
            self.provider, self.model, self.request_id,
            self.tenant_id, self.unit_id,
        )
        if (
            any(not isinstance(x, str) or not 1 <= len(x) <= 128 for x in values)
            or not isinstance(self.evidence_digest, str)
            or re.fullmatch("[a-f0-9]{64}", self.evidence_digest) is None
            or type(self.no_charge) is not bool
            or type(self.input_tokens) is not int
            or type(self.output_tokens) is not int
            or self.input_tokens < 0 or self.output_tokens < 0
            or (self.no_charge and (self.input_tokens or self.output_tokens))
        ):
            raise QuotaDenied("core_usage_receipt_invalid")
        if self.provider_cost_usd is not None and (
            not isinstance(self.provider_cost_usd, Decimal)
            or not self.provider_cost_usd.is_finite()
            or self.provider_cost_usd < 0
            or (self.no_charge and self.provider_cost_usd != 0)
        ):
            raise QuotaDenied("core_usage_cost_invalid")


def recovery_bundle_from_verified_receipt(
    receipt: VerifiedProviderUsageReceipt, *,
    request_policy_revision: int,
    tokens_policy_revision: int,
    request_scope: str = "__tenant__",
    tokens_scope: str = "__tenant__",
) -> tuple[QuotaRequirement, ...]:
    """Construct exact two-metric input for existing governed Core recovery.

    No-charge MUST originate from a positively confirmed no-charge attestation,
    never a timeout, a missing receipt, or failed provider response.
    """
    if (
        type(request_policy_revision) is not int
        or type(tokens_policy_revision) is not int
        or request_policy_revision < 1 or tokens_policy_revision < 1
        or request_scope not in {receipt.unit_id, "__tenant__"}
        or tokens_scope not in {receipt.unit_id, "__tenant__"}
    ):
        raise QuotaDenied("core_usage_receipt_policy_invalid")
    requests = 0 if receipt.no_charge else 1
    tokens = receipt.input_tokens + receipt.output_tokens
    if not receipt.no_charge and tokens <= 0:
        raise QuotaDenied("core_usage_receipt_tokens_unknown")
    if tokens > 2_000_000_000:
        raise QuotaDenied("core_usage_receipt_tokens_excessive")
    return (
        QuotaRequirement(
            tenant_id=receipt.tenant_id, unit_id=request_scope,
            capability="ai.requests", units=requests,
            policy_revision=request_policy_revision,
        ),
        QuotaRequirement(
            tenant_id=receipt.tenant_id, unit_id=tokens_scope,
            capability="ai.total_tokens", units=tokens,
            policy_revision=tokens_policy_revision,
        ),
    )
