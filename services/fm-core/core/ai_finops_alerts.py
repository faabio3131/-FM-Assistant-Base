"""Read-only FinOps alerts on canonical, per-attempt Core usage evidence.

Never interpret an absent price/receipt as a zero-dollar provider charge.
This module does NOT settle invoices, release quota or send notifications.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.ai_usage_ledger import AIRequestCostSummary


@dataclass(frozen=True, kw_only=True)
class CostAlertEvaluation:
    status: str
    reasons: tuple[str, ...]
    known_cost: Decimal
    cost_currency: str | None
    unknown_attempts: int
    observed_attempts: int
    all_costs_known: bool


def evaluate_request_cost_alert(
    summary: AIRequestCostSummary, *,
    maximum_known_cost: Decimal | None = None,
    currency: str | None = None,
) -> CostAlertEvaluation:
    if maximum_known_cost is not None and (
        not isinstance(maximum_known_cost, Decimal)
        or not maximum_known_cost.is_finite()
        or maximum_known_cost <= 0
        or not isinstance(currency, str)
        or len(currency) != 3 or not currency.isascii() or not currency.isalpha()
        or (summary.currency is not None and summary.currency != currency.upper())
    ):
        raise ValueError("finops.alert_policy_invalid")
    reasons: list[str] = []
    if summary.total_attempts == 0:
        reasons.append("usage_evidence_unavailable")
    if summary.unknown_attempts > 0:
        reasons.append("provider_cost_unverified")
    if (
        maximum_known_cost is not None
        and summary.known_total > maximum_known_cost
    ):
        reasons.append("known_subtotal_above_limit")
    status = (
        "needs_attention" if reasons else
        "reconciled"
    )
    return CostAlertEvaluation(
        status=status, reasons=tuple(reasons),
        known_cost=summary.known_total,
        cost_currency=summary.currency,
        unknown_attempts=summary.unknown_attempts,
        observed_attempts=summary.total_attempts,
        all_costs_known=summary.all_recorded_costs_known,
    )
