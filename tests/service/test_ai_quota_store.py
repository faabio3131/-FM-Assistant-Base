"""F3.8 quota policy ledger regression with synthetic units only."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase
from core.ai_quota_store import (
    AIQuotaPolicyRecord,
    AIQuotaReservationRecord,
    QuotaDenied,
    QuotaRequirement,
    QuotaReservations,
    ReservationState,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def quota(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'quotas.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        for tenant, unit, limit in (("a", "u1", 3), ("a", "u2", 1), ("b", "u1", 1), ("b", "u2", 1)):
            db.add(AIQuotaPolicyRecord(
                tenant_id=tenant, unit_id=unit, capability="text",
                limit_units=limit, window_seconds=60, revision=1,
            ))
    yield QuotaReservations(sessions), sessions
    engine.dispose()


def reserve(store, rid, *, tenant="a", unit="u1", units=1, at=NOW):
    return store.reserve(
        tenant_id=tenant, unit_id=unit, capability="text",
        request_id=rid, units=units, at=at,
    )


def settle(store, rid, *, tenant="a", unit="u1", consumed=0):
    return store.settle(
        tenant_id=tenant, unit_id=unit, capability="text",
        request_id=rid, consumed_units=consumed,
    )


def test_reservation_idempotency_conflict_and_quota_cap(quota):
    store, sessions = quota
    one = reserve(store, "request-1", units=2)
    assert one.state == ReservationState.RESERVED
    assert reserve(store, "request-1", units=2).request_id == one.request_id
    with pytest.raises(QuotaDenied, match="request_conflict"):
        reserve(store, "request-1", units=1)
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "request-2", units=2)
    assert reserve(store, "request-2", units=1).reserved_units == 1
    with sessions() as db:
        assert len(db.scalars(select(AIQuotaReservationRecord)).all()) == 2


def test_settlement_refund_and_double_settlement_are_idempotent(quota):
    store, _ = quota
    reserve(store, "first", units=3)
    assert settle(store, "first", consumed=1).state == ReservationState.SETTLED
    assert settle(store, "first", consumed=1).consumed_units == 1
    with pytest.raises(QuotaDenied, match="settlement_conflict"):
        settle(store, "first", consumed=2)
    assert reserve(store, "second", units=2).state == ReservationState.RESERVED
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "third", units=1)
    settle(store, "second", consumed=0)
    assert reserve(store, "third", units=1).state == ReservationState.RESERVED


def test_no_cross_scope_release_or_shared_budget(quota):
    store, _ = quota
    reserve(store, "same-id", tenant="a", unit="u1", units=3)
    reserve(store, "same-id", tenant="b", unit="u1")
    reserve(store, "same-id", tenant="a", unit="u2")
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        settle(store, "same-id", tenant="b", unit="u2")
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "another", tenant="b", unit="u1")


def test_request_id_cannot_shift_to_next_period(quota):
    store, _ = quota
    reserve(store, "same", units=1)
    with pytest.raises(QuotaDenied, match="request_conflict"):
        reserve(store, "same", units=1, at=NOW + timedelta(minutes=2))
    assert reserve(store, "next", units=3, at=NOW + timedelta(minutes=2)).period != (
        reserve(store, "same").period
    )


def test_fail_closed_for_bad_policy_or_request(quota):
    store, _ = quota
    with pytest.raises(QuotaDenied, match="policy_unavailable"):
        reserve(store, "unknown", tenant="missing")
    with pytest.raises(QuotaDenied, match="invalid_scope"):
        reserve(store, "../spoofed")
    with pytest.raises(QuotaDenied, match="invalid_units"):
        reserve(store, "test", units=0)
    with pytest.raises(QuotaDenied, match="invalid_units"):
        reserve(store, "test", units=True)
    with pytest.raises(QuotaDenied, match="time_invalid"):
        reserve(store, "test", at=datetime(2026, 10, 18))
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        settle(store, "never")
    reserve(store, "only", units=1)
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        settle(store, "only", consumed=2)


def test_request_replay_after_policy_revision_is_rejected(quota):
    store, sessions = quota
    reserve(store, "prior", units=1)
    with sessions.begin() as db:
        policy = db.get(AIQuotaPolicyRecord, ("a", "u1", "text"))
        policy.revision = 2
        policy.limit_units = 1
    with pytest.raises(QuotaDenied, match="request_conflict"):
        reserve(store, "prior", units=1)
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "new", units=1)


def test_pending_quota_reconciliation_is_scoped_read_only(quota):
    store, sessions = quota
    reserve(store, "ambiguous", units=1, tenant="a", unit="u1")
    reserve(store, "other-tenant", tenant="b", unit="u1")
    reserve(store, "success", units=1, tenant="a", unit="u1")
    settle(store, "success", consumed=1, tenant="a", unit="u1")
    cutoff = NOW + timedelta(minutes=1)
    pending = store.pending_for_reconciliation(
        tenant_id="a", unit_id="u1", capability="text", older_than=cutoff,
    )
    assert [p.request_id for p in pending] == ["ambiguous"]
    assert store.pending_for_reconciliation(
        tenant_id="a", unit_id="u2", capability="text", older_than=cutoff,
    ) == ()
    assert [p.request_id for p in store.pending_for_reconciliation(
        tenant_id="b", unit_id="u1", capability="text", older_than=cutoff,
    )] == ["other-tenant"]
    with pytest.raises(QuotaDenied, match="invalid_limit"):
        store.pending_for_reconciliation(
            tenant_id="a", unit_id="u1", capability="text",
            older_than=cutoff, limit=1000,
        )
    with sessions() as db:
        records = db.scalars(select(AIQuotaReservationRecord)).all()
        assert len(records) == 3  # query did not modify/erase reservations


def test_atomic_multimetric_plan_reservation_and_settlement(quota):
    store, sessions = quota
    with sessions.begin() as db:
        for scope, metric, limit in (
            ("__tenant__", "ai.total_tokens", 1000),
            ("u1", "ai.requests", 2),
        ):
            db.add(AIQuotaPolicyRecord(
                tenant_id="a", unit_id=scope, capability=metric,
                limit_units=limit, window_seconds=60, revision=1,
            ))
    needs = (
        QuotaRequirement(
            tenant_id="a", unit_id="__tenant__",
            capability="ai.total_tokens", units=600,
        ),
        QuotaRequirement(
            tenant_id="a", unit_id="u1", capability="ai.requests", units=1,
        ),
    )
    store.reserve_bundle(needs=needs, request_id="req-metric", at=NOW)
    with pytest.raises(QuotaDenied, match="execution_replay_denied"):
        store.reserve_bundle(needs=needs, request_id="req-metric", at=NOW)
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        store.reserve_bundle(
            needs=(
                QuotaRequirement(
                    tenant_id="a", unit_id="__tenant__",
                    capability="ai.total_tokens", units=600,
                ),
                QuotaRequirement(
                    tenant_id="a", unit_id="u1", capability="ai.requests", units=1,
                ),
            ),
            request_id="req-over", at=NOW,
        )
    with sessions() as db:
        assert len(db.scalars(
            select(AIQuotaReservationRecord).where(
                AIQuotaReservationRecord.request_id == "req-over",
            ),
        ).all()) == 0  # failure rolled back every metric

    store.settle_bundle(
        request_id="req-metric",
        usage=(
            QuotaRequirement(
                tenant_id="a", unit_id="__tenant__",
                capability="ai.total_tokens", units=350,
            ),
            QuotaRequirement(
                tenant_id="a", unit_id="u1", capability="ai.requests", units=1,
            ),
        ),
    )
    store.reserve_bundle(
        needs=(
            QuotaRequirement(
                tenant_id="a", unit_id="__tenant__",
                capability="ai.total_tokens", units=650,
            ),
        ),
        request_id="next-request", at=NOW,
    )
    with pytest.raises(QuotaDenied, match="settlement_conflict"):
        store.settle_bundle(
            request_id="req-metric",
            usage=(
                QuotaRequirement(
                    tenant_id="a", unit_id="__tenant__",
                    capability="ai.total_tokens", units=200,
                ),
            ),
        )


def test_bundle_cross_tenant_and_partial_settlement_denied(quota):
    store, sessions = quota
    with pytest.raises(QuotaDenied, match="bundle_invalid"):
        store.reserve_bundle(
            needs=(
                QuotaRequirement(
                    tenant_id="a", unit_id="u1", capability="text", units=1,
                ),
                QuotaRequirement(
                    tenant_id="b", unit_id="u1", capability="text", units=1,
                ),
            ),
            request_id="cross-tenant", at=NOW,
        )
    store.reserve_bundle(
        needs=(
            QuotaRequirement(tenant_id="a", unit_id="u1", capability="text", units=1),
            QuotaRequirement(tenant_id="a", unit_id="u2", capability="text", units=1),
        ),
        request_id="multi-scope", at=NOW,
    )
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        store.settle_bundle(
            request_id="multi-scope",
            usage=(
                QuotaRequirement(tenant_id="a", unit_id="u1", capability="text", units=1),
                QuotaRequirement(tenant_id="a", unit_id="u2", capability="text", units=2),
            ),
        )
    with sessions() as db:
        records = db.scalars(
            select(AIQuotaReservationRecord).where(
                AIQuotaReservationRecord.request_id == "multi-scope",
            ),
        ).all()
        assert len(records) == 2
        assert all(record.state == ReservationState.RESERVED for record in records)


def test_plan_usage_snapshot_reports_remaining_and_pending_reservations(quota):
    store, _ = quota
    reserve(store, "first", units=2)
    before = store.usage_snapshot(
        tenant_id="a", unit_id="u1", capability="text", at=NOW,
    )
    assert (before.limit_units, before.reserved_units, before.consumed_units) == (3, 2, 0)
    assert before.remaining_units == 1
    assert before.period_ends_at > NOW
    settle(store, "first", consumed=1)
    after = store.usage_snapshot(
        tenant_id="a", unit_id="u1", capability="text", at=NOW,
    )
    assert (after.reserved_units, after.consumed_units, after.remaining_units) == (0, 1, 2)
    other = store.usage_snapshot(
        tenant_id="b", unit_id="u1", capability="text", at=NOW,
    )
    assert (other.reserved_units, other.consumed_units, other.remaining_units) == (0, 0, 1)
    with pytest.raises(QuotaDenied, match="policy_unavailable"):
        store.usage_snapshot(
            tenant_id="missing", unit_id="u1", capability="text", at=NOW,
        )
