from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from core.ai_finops_preflight import (
    CostPolicy,
    FinOpsPreflightDenied,
    TokenCeiling,
    verify_cost_preflight,
)
from core.ai_pricing import CatalogoPrecosIAEmMemoria, PriceSnapshotIA, TarifaIA
from core.ai_router import CapabilityIA, RotaIA

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


def route(index: int) -> RotaIA:
    return RotaIA(
        configuracao_id=f"r-{index}", provider="openai", model=f"model-{index}",
        capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        prioridade=100 - index, price_snapshot_id=f"price-{index}",
    )


def snapshot(index: int) -> PriceSnapshotIA:
    return PriceSnapshotIA(
        price_snapshot_id=f"price-{index}", provider="openai", model=f"model-{index}",
        modalidade="text", moeda="USD", versao=1,
        vigencia_inicio=datetime(2025, 1, 1, tzinfo=UTC),
        vigencia_fim=None,
        tarifas=(
            TarifaIA(
                componente="input_tokens", preco=Decimal("0.02"),
                unidades_por_preco=1000,
            ),
            TarifaIA(
                componente="output_tokens", preco=Decimal("0.03"),
                unidades_por_preco=1000,
            ),
        ),
    )


def estimate(*, budget="0.1", catalog=None, routes=None, ceilings=None):
    actual_routes = routes if routes is not None else (route(1), route(2))
    actual_ceilings = ceilings if ceilings is not None else (
        TokenCeiling(route_id="r-1", input_tokens=1000, output_tokens=1000),
        TokenCeiling(route_id="r-2", input_tokens=1000, output_tokens=1000),
    )
    source = catalog if catalog is not None else CatalogoPrecosIAEmMemoria(
        (snapshot(1), snapshot(2)),
    )
    return verify_cost_preflight(
        routes=actual_routes, ceilings=actual_ceilings,
        catalog=source,
        policy=CostPolicy(currency="usd", maximum_request_cost=Decimal(budget)),
        now=NOW,
    )


def test_cost_preflight_accounts_for_every_fallback_route():
    verified = estimate()
    assert verified.worst_case_cost == Decimal("0.10")
    assert verified.currency == "USD"
    assert verified.price_snapshot_ids == ("price-1", "price-2")
    assert verified.route_costs == (
        ("r-1", Decimal("0.05")), ("r-2", Decimal("0.05")),
    )
    with pytest.raises(FinOpsPreflightDenied, match="request_budget_exceeded"):
        estimate(budget="0.09")


def test_unknown_tariffs_and_snapshot_refuse_admission():
    with pytest.raises(FinOpsPreflightDenied, match="price_unknown"):
        estimate(catalog=CatalogoPrecosIAEmMemoria((snapshot(1),)))
    incomplete = replace(snapshot(2), tarifas=(
        TarifaIA(
            componente="input_tokens", preco=Decimal("0.02"),
            unidades_por_preco=1000,
        ),
    ))
    with pytest.raises(FinOpsPreflightDenied, match="price_unknown"):
        estimate(catalog=CatalogoPrecosIAEmMemoria((snapshot(1), incomplete)))


def test_scope_currency_and_coverage_validation():
    with pytest.raises(FinOpsPreflightDenied, match="price_scope_or_currency_invalid"):
        estimate(catalog=CatalogoPrecosIAEmMemoria((
            snapshot(1), replace(snapshot(2), moeda="BRL"),
        )))
    with pytest.raises(FinOpsPreflightDenied, match="route_coverage_incomplete"):
        estimate(ceilings=(TokenCeiling(
            route_id="r-1", input_tokens=1000, output_tokens=1000,
        ),))
    with pytest.raises(FinOpsPreflightDenied, match="route_coverage_incomplete"):
        estimate(routes=(route(1), route(1)))


@pytest.mark.parametrize("units", [-1, True, 1.5, 1_000_000_001])
def test_invalid_token_estimates_are_denied(units):
    with pytest.raises(FinOpsPreflightDenied, match="token_ceiling_invalid"):
        TokenCeiling(route_id="r-1", input_tokens=units, output_tokens=1)


@pytest.mark.parametrize("limit", ["0", "-1", "NaN", "Infinity"])
def test_invalid_cost_limits_are_denied(limit):
    with pytest.raises(FinOpsPreflightDenied, match="cost_limit_invalid"):
        CostPolicy(currency="USD", maximum_request_cost=Decimal(limit))


def test_explicit_cached_token_tariff_is_required_when_present():
    ceilings = (
        TokenCeiling(route_id="r-1", input_tokens=1000, output_tokens=1000),
        TokenCeiling(route_id="r-2", input_tokens=1000, output_tokens=1000, cached_tokens=1),
    )
    with pytest.raises(FinOpsPreflightDenied, match="price_unknown"):
        estimate(ceilings=ceilings)
