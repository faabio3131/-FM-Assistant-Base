from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase
from core.ai_pricing import PriceSnapshotIA, SnapshotPrecoDuplicado, TarifaIA
from core.ai_router import AIUsageEvent, CapabilityIA, OutcomeIA
from core.ai_usage_ledger import PersistentAIFinOps


@pytest.fixture
def ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    yield PersistentAIFinOps(sessions), sessions
    engine.dispose()


def price():
    return PriceSnapshotIA(
        price_snapshot_id="price-1",
        provider="openai",
        model="model-1",
        modalidade="text",
        moeda="USD",
        versao=1,
        vigencia_inicio=datetime(2025, 1, 1, tzinfo=UTC),
        vigencia_fim=None,
        tarifas=(
            TarifaIA(componente="input_tokens", preco=Decimal("0.02"), unidades_por_preco=1000),
            TarifaIA(componente="output_tokens", preco=Decimal("0.03"), unidades_por_preco=1000),
        ),
    )


def event(*, tenant="a", unit="u", request="req-1", price_id="price-1", inp=1000, out=1000):
    return AIUsageEvent(
        tenant_id=tenant,
        unidade_id=unit,
        request_id=request,
        correlation_id="correlation-1",
        capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        provider="openai",
        model="model-1",
        route_reason="capability=text;priority=100",
        fallback_used=False,
        fallback_reason=None,
        input_tokens=inp,
        output_tokens=out,
        cached_tokens=None,
        latency_ms=25,
        outcome=OutcomeIA.SUCESSO,
        custo_real_calculado=None,
        moeda=None,
        price_snapshot_id=price_id,
        timestamp=datetime(2026, 10, 18, 12, tzinfo=UTC),
    )


def _list(ledger, tenant="a", unit="u"):
    return ledger.listar(
        tenant_id=tenant,
        unidade_id=unit,
        inicio=date(2026, 10, 18),
        fim=date(2026, 10, 18),
    )


def test_price_snapshot_and_exact_cost_persist(ledger):
    store, sessions = ledger
    store.add_price_snapshot(price())
    store.registrar(event())
    clone = PersistentAIFinOps(sessions)
    buckets = _list(clone)
    assert len(buckets) == 1
    assert buckets[0].attempts == 1
    assert buckets[0].moeda == "USD"
    assert buckets[0].cost_total == Decimal("0.05")
    assert buckets[0].cost_known_events == 1
    assert buckets[0].cost_unknown_events == 0


def test_events_are_idempotent_per_request_and_attempt(ledger):
    store, _ = ledger
    store.add_price_snapshot(price())
    store.registrar(event())
    store.registrar(event())
    assert _list(store)[0].attempts == 1


def test_missing_prices_and_tokens_are_explicitly_unknown(ledger):
    store, _ = ledger
    store.registrar(event(price_id="missing"))
    unknown = _list(store)[0]
    assert unknown.cost_known_events == 0
    assert unknown.cost_unknown_events == 1
    assert unknown.moeda == "XXX"
    store.add_price_snapshot(price())
    store.registrar(event(request="req-2", inp=None))
    with_tokens_missing = _list(store)
    assert len(with_tokens_missing) == 2
    known_currency_unknown_cost = next(x for x in with_tokens_missing if x.moeda == "USD")
    assert known_currency_unknown_cost.cost_unknown_events == 1
    assert known_currency_unknown_cost.cost_total == 0


def test_tenant_and_unit_isolation_is_mandatory(ledger):
    store, _ = ledger
    store.add_price_snapshot(price())
    store.registrar(event(tenant="a", unit="u", request="x"))
    store.registrar(event(tenant="b", unit="u", request="y"))
    store.registrar(event(tenant="a", unit="other", request="z"))
    assert _list(store, "a", "u")[0].attempts == 1
    assert _list(store, "b", "u")[0].attempts == 1
    assert _list(store, "a", "other")[0].attempts == 1
    assert _list(store, "b", "other") == ()


def test_price_snapshot_is_append_only_through_repository(ledger):
    store, _ = ledger
    store.add_price_snapshot(price())
    with pytest.raises(SnapshotPrecoDuplicado):
        store.add_price_snapshot(price())


def test_invalid_date_range_fails_closed(ledger):
    store, _ = ledger
    with pytest.raises(ValueError, match="invalid_scope_or_interval"):
        store.listar(
            tenant_id="a",
            unidade_id="u",
            inicio=date(2026, 10, 19),
            fim=date(2026, 10, 18),
        )
