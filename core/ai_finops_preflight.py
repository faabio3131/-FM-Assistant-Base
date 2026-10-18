"""Deterministic worst-case cost preflight for governed provider attempts.

This is a pure internal building block. It cannot prove a provider enforces
the token ceilings until adapter-level caps and authoritative input metering
are wired and tested. Unknown pricing is DENIED, never treated as free.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.ai_cost import CalculadoraCustoIA, OrigemCustoIA
from core.ai_pricing import CatalogoPrecosIA, SnapshotPrecoAusente
from core.ai_router import RotaIA


class FinOpsPreflightDenied(ValueError):
    """Safe policy-denied outcome that contains no provider credentials."""


@dataclass(frozen=True, kw_only=True)
class TokenCeiling:
    route_id: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0

    def __post_init__(self) -> None:
        if not self.route_id or len(self.route_id) > 128:
            raise FinOpsPreflightDenied("finops.route_invalid")
        for count in (self.input_tokens, self.output_tokens, self.cached_tokens):
            if type(count) is not int or not 0 <= count <= 1_000_000_000:
                raise FinOpsPreflightDenied("finops.token_ceiling_invalid")


@dataclass(frozen=True, kw_only=True)
class CostPolicy:
    currency: str
    maximum_request_cost: Decimal

    def __post_init__(self) -> None:
        if (
            not isinstance(self.currency, str)
            or len(self.currency) != 3
            or not self.currency.isascii()
            or not self.currency.isalpha()
        ):
            raise FinOpsPreflightDenied("finops.currency_invalid")
        if (
            not isinstance(self.maximum_request_cost, Decimal)
            or not self.maximum_request_cost.is_finite()
            or self.maximum_request_cost <= 0
        ):
            raise FinOpsPreflightDenied("finops.cost_limit_invalid")
        object.__setattr__(self, "currency", self.currency.upper())


@dataclass(frozen=True, kw_only=True)
class CostPreflight:
    currency: str
    worst_case_cost: Decimal
    route_costs: tuple[tuple[str, Decimal], ...]
    price_snapshot_ids: tuple[str, ...]


def verify_cost_preflight(
    *,
    routes: tuple[RotaIA, ...],
    ceilings: tuple[TokenCeiling, ...],
    catalog: CatalogoPrecosIA,
    policy: CostPolicy,
    now: datetime,
) -> CostPreflight:
    """Reject missing route ceilings, unknown tariffs and over-budget fallback.

    Worst-case sum assumes every configured route could be attempted. This
    does not reserve monetary budget, enforce provider token caps or settle
    actual usage; those are separate required internal construction gates.
    """
    if not routes or len(routes) != len(ceilings):
        raise FinOpsPreflightDenied("finops.route_coverage_incomplete")
    ids = [route.configuracao_id for route in routes]
    bound_ids = [ceiling.route_id for ceiling in ceilings]
    if len(set(ids)) != len(ids) or sorted(ids) != sorted(bound_ids):
        raise FinOpsPreflightDenied("finops.route_coverage_incomplete")
    calculator = CalculadoraCustoIA()
    costs: list[tuple[str, Decimal]] = []
    snapshots: list[str] = []
    ceilings_by_id = {item.route_id: item for item in ceilings}
    for route in routes:
        try:
            snapshot = catalog.obter_snapshot(price_snapshot_id=route.price_snapshot_id)
        except SnapshotPrecoAusente as exc:
            raise FinOpsPreflightDenied("finops.price_unknown") from exc
        if (
            snapshot.provider != route.provider
            or snapshot.model != route.model
            or snapshot.moeda != policy.currency
            or not snapshot.vigente_em(now)
        ):
            raise FinOpsPreflightDenied("finops.price_scope_or_currency_invalid")
        tokens = ceilings_by_id[route.configuracao_id]
        cost = calculator.estimar_tokens(
            snapshot=snapshot,
            input_tokens=tokens.input_tokens,
            output_tokens=tokens.output_tokens,
            cached_tokens=tokens.cached_tokens,
        )
        if (
            cost.origem is OrigemCustoIA.INDISPONIVEL
            or cost.valor is None
            or not cost.valor.is_finite()
            or cost.valor < 0
        ):
            raise FinOpsPreflightDenied("finops.price_unknown")
        costs.append((route.configuracao_id, cost.valor))
        snapshots.append(route.price_snapshot_id)
    total = sum((amount for _, amount in costs), Decimal(0))
    if total > policy.maximum_request_cost:
        raise FinOpsPreflightDenied("finops.request_budget_exceeded")
    return CostPreflight(
        currency=policy.currency,
        worst_case_cost=total,
        route_costs=tuple(costs),
        price_snapshot_ids=tuple(snapshots),
    )
