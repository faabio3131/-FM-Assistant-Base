"""Plan franchise authorization uses disposable DB and synthetic usage."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase
from core.ai_plan_usage_guard import PlanQuotaPolicy, PlanUsageGuard
from core.ai_quota_store import AIQuotaPolicyRecord, QuotaDenied, QuotaReservations
from core.ai_router import (
    AIUsageEvent,
    CapabilityIA,
    OutcomeIA,
    SolicitacaoIA,
)

NOW = datetime(2026, 10, 18, 20, tzinfo=UTC)


class Authority:
    def __init__(self, tenant="a", cutoff=None):
        self.tenant = tenant
        self.cutoff = cutoff or NOW + timedelta(days=1)

    def resolve(self, *, tenant_id, unit_id, capability, now):
        return PlanQuotaPolicy(
            tenant_id=self.tenant, unit_id=unit_id, plan_code="FM_ALL_FEATURES",
            revision=1, valid_until=self.cutoff,
            input_bound=100, output_bound=80,
            scopes=(
                ("ai.requests", "tenant"),
                ("ai.total_tokens", "tenant"),
                ("ai.input_tokens", "unit"),
                ("ai.output_tokens", "unit"),
            ),
        )


@pytest.fixture()
def guarded(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'plan-franchise.sqlite'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        for tenant in ("a", "b"):
            for metric, unit, ceiling in (
                ("ai.requests", "__tenant__", 2),
                ("ai.total_tokens", "__tenant__", 300),
                ("ai.input_tokens", "u1", 300),
                ("ai.output_tokens", "u1", 200),
            ):
                db.add(AIQuotaPolicyRecord(
                    tenant_id=tenant, unit_id=unit, capability=metric,
                    limit_units=ceiling, window_seconds=86400, revision=1,
                ))
    store = QuotaReservations(sessions)
    yield PlanUsageGuard(quota=store, authority=Authority()), store
    engine.dispose()


def request(rid="r-1", tenant="a"):
    return SolicitacaoIA(
        tenant_id=tenant, unidade_id="u1", request_id=rid,
        correlation_id=rid, capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        conteudo={"test": "test"},
    )


def event(req, *, inp=20, out=10, cached=5, fallback=False):
    return AIUsageEvent(
        tenant_id=req.tenant_id, unidade_id=req.unidade_id,
        request_id=req.request_id, correlation_id=req.correlation_id,
        capability=req.capability, provider="synthetic-provider", model="fake-model",
        route_reason="test", fallback_used=fallback, fallback_reason=None,
        input_tokens=inp, output_tokens=out, cached_tokens=cached,
        latency_ms=1, outcome=OutcomeIA.SUCESSO,
        custo_real_calculado=None, moeda=None, price_snapshot_id="test",
        timestamp=NOW,
    )


def test_admit_reconcile_and_partial_refund(guarded):
    guard, store = guarded
    req = request()
    policy = guard.admit(request=req, at=NOW)
    snapshot = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert snapshot.reserved_units == 180 and snapshot.remaining_units == 120
    assert guard.reconcile(request=req, policy=policy, events=(event(req),))
    after = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert after.reserved_units == 0 and after.consumed_units == 30
    assert after.remaining_units == 270
    with pytest.raises(QuotaDenied, match="execution_replay_denied"):
        guard.admit(request=req, at=NOW)


def test_concurrent_budget_limit_and_unknown_metering_remain_reserved(guarded):
    guard, store = guarded
    req = request()
    policy = guard.admit(request=req, at=NOW)
    assert not guard.reconcile(
        request=req, policy=policy, events=(event(req, inp=None),),
    )
    snapshot = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert snapshot.reserved_units == 180
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        guard.admit(request=request("r-2"), at=NOW)


def test_cross_tenant_projection_and_expired_license_denied(guarded):
    _, store = guarded
    guard = PlanUsageGuard(quota=store, authority=Authority(tenant="b"))
    with pytest.raises(QuotaDenied, match="license_unavailable"):
        guard.admit(request=request(), at=NOW)
    expired = PlanUsageGuard(quota=store, authority=Authority(cutoff=NOW))
    with pytest.raises(QuotaDenied, match="license_unavailable"):
        expired.admit(request=request(), at=NOW)


def test_fallback_totals_count_both_attempts_and_cache_not_double_counted(guarded):
    guard, store = guarded
    req = request()
    policy = guard.admit(request=req, at=NOW)
    assert guard.reconcile(request=req, policy=policy, events=(
        event(req,inp=20,out=10,cached=5),
        event(req,inp=25,out=15,cached=10,fallback=True),
    ))
    snapshot = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert snapshot.consumed_units == 70  # 20+10+25+15; cached is within input


def test_overspend_is_never_silently_reconciled(guarded):
    guard, store = guarded
    req = request()
    policy = guard.admit(request=req, at=NOW)
    with pytest.raises(QuotaDenied, match="actual_usage_exceeds_reserved"):
        guard.reconcile(
            request=req, policy=policy, events=(event(req,inp=101,out=0,cached=0),),
        )
    assert store.usage_snapshot(
        tenant_id="a",unit_id="__tenant__",
        capability="ai.total_tokens",at=NOW,
    ).reserved_units == 180


def test_negative_attempt_usage_cannot_cancel_real_consumption(guarded):
    guard, store = guarded
    req = request()
    policy = guard.admit(request=req, at=NOW)
    assert not guard.reconcile(request=req, policy=policy, events=(
        event(req, inp=70, out=20, cached=5),
        event(req, inp=-50, out=0, cached=0, fallback=True),
    ))
    snapshot = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__", capability="ai.total_tokens", at=NOW,
    )
    assert snapshot.reserved_units == 180
    assert snapshot.consumed_units == 0


def test_boolean_plan_revision_is_not_valid_policy():
    with pytest.raises(QuotaDenied, match="policy_invalid"):
        PlanQuotaPolicy(
            tenant_id="a", unit_id="u1", plan_code="all", revision=True,
            valid_until=NOW + timedelta(days=1), input_bound=100,
            output_bound=80,
            scopes=(("ai.requests", "tenant"), ("ai.total_tokens", "tenant")),
        )
