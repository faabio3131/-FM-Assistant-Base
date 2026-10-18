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
        for tenant, unit, limit in (("a", "u1", 3), ("a", "u2", 1), ("b", "u1", 1)):
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
