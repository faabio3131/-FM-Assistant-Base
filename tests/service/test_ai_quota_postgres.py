"""PostgreSQL 16 concurrency gate for F3.8 quotas (disposable CI only)."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from alembic import command
from core.ai_circuit_breaker import CircuitDenied, CircuitPhase, CircuitPolicy
from core.ai_circuit_state_store import PersistentCircuit, ProviderCircuitRecord
from core.ai_control_plane import AIProvider
from core.ai_quota_store import (
    AIQuotaPolicyRecord,
    AIQuotaReservationRecord,
    QuotaDenied,
    QuotaRequirement,
    QuotaReservations,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def postgres_quota():
    url = os.environ.get("FM_CORE_F3_POSTGRES_TEST_URL", "")
    if not url:
        pytest.skip("requires disposable PostgreSQL CI database")
    if not url.startswith("postgresql+psycopg://") or "/core_f3" not in url:
        pytest.fail("unsafe test database URL")
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url, pool_size=6, max_overflow=4, pool_timeout=10)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.query(AIQuotaReservationRecord).delete()
        db.query(AIQuotaPolicyRecord).delete()
        db.add(AIQuotaPolicyRecord(
            tenant_id="tenant-a", unit_id="unit-a", capability="text",
            limit_units=1, window_seconds=60, revision=1,
        ))
    try:
        yield QuotaReservations(sessions), sessions
    finally:
        engine.dispose()


def test_pg_concurrent_reservation_serializes_budget(postgres_quota):
    store, sessions = postgres_quota
    barrier = Barrier(2)

    def claim(request_id: str) -> str:
        barrier.wait(timeout=8)
        try:
            store.reserve(
                tenant_id="tenant-a", unit_id="unit-a", capability="text",
                request_id=request_id, units=1, at=NOW,
            )
            return "admitted"
        except QuotaDenied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(claim, "req-a")
        b = pool.submit(claim, "req-b")
        outcomes = [a.result(timeout=20), b.result(timeout=20)]
    assert sorted(outcomes) == ["admitted", "denied"]
    with sessions() as db:
        rows = db.scalars(select(AIQuotaReservationRecord)).all()
        assert len(rows) == 1
        assert rows[0].reserved_units == 1


def test_pg_same_request_is_idempotent_across_two_workers(postgres_quota):
    store, sessions = postgres_quota
    barrier = Barrier(2)

    def claim() -> str:
        barrier.wait(timeout=8)
        return store.reserve(
            tenant_id="tenant-a", unit_id="unit-a", capability="text",
            request_id="stable-id", units=1, at=NOW,
        ).request_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(claim), pool.submit(claim)
        assert a.result(timeout=20) == b.result(timeout=20) == "stable-id"
    with sessions() as db:
        assert len(db.scalars(select(AIQuotaReservationRecord)).all()) == 1


def test_pg_circuit_only_one_half_open_claim(postgres_quota):
    """Two independent workers contend for a single provider probe lease."""
    _, sessions = postgres_quota
    with sessions.begin() as db:
        provider = db.get(AIProvider, "provider-ci")
        if provider is None:
            db.add(AIProvider(
                provider_id="provider-ci", adapter="gemini",
                base_url="https://invalid.example", enabled=True,
            ))
        db.flush()
        row = db.get(ProviderCircuitRecord, "provider-ci")
        if row is None:
            db.add(ProviderCircuitRecord(
                provider_id="provider-ci", phase="open", failures=2,
                until=NOW, probe_id=None, version=1,
            ))
        else:
            row.phase = "open"
            row.failures = 2
            row.until = NOW
            row.probe_id = None
            row.version += 1
    store = PersistentCircuit(
        sessions, CircuitPolicy(threshold=2, cooldown_seconds=30, probe_seconds=5),
    )
    barrier = Barrier(2)

    def attempt():
        barrier.wait(timeout=8)
        try:
            return "claimed" if store.claim(
                provider_id="provider-ci", now=NOW,
            )[0] else "unexpected"
        except CircuitDenied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(attempt), pool.submit(attempt)
        assert sorted((a.result(timeout=20), b.result(timeout=20))) == [
            "claimed", "denied",
        ]
    with sessions() as db:
        row = db.get(ProviderCircuitRecord, "provider-ci")
        assert row.phase == CircuitPhase.HALF_OPEN
        assert row.probe_id


def test_pg_shared_tenant_budget_across_units_is_atomic(postgres_quota):
    """Parallel units cannot evade a shared plan-wide token ceiling."""
    store, sessions = postgres_quota
    with sessions.begin() as db:
        for scope, metric, limit in (
            ("__tenant__", "ai.total_tokens", 1000),
            ("unit-a", "ai.requests", 5),
            ("unit-b", "ai.requests", 5),
        ):
            key = ("tenant-budget-ci", scope, metric)
            old = db.get(AIQuotaPolicyRecord, key)
            if old is None:
                db.add(AIQuotaPolicyRecord(
                    tenant_id=key[0], unit_id=key[1], capability=key[2],
                    limit_units=limit, window_seconds=60, revision=1,
                ))
        db.flush()
    barrier = Barrier(2)

    def reserve(unit: str) -> str:
        barrier.wait(timeout=8)
        try:
            store.reserve_bundle(
                request_id=f"request-{unit}", at=NOW,
                needs=(
                    QuotaRequirement(
                        tenant_id="tenant-budget-ci", unit_id=unit,
                        capability="ai.requests", units=1,
                    ),
                    QuotaRequirement(
                        tenant_id="tenant-budget-ci", unit_id="__tenant__",
                        capability="ai.total_tokens", units=700,
                    ),
                ),
            )
            return "accepted"
        except QuotaDenied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(reserve, "unit-a")
        second = pool.submit(reserve, "unit-b")
        assert sorted((first.result(timeout=20), second.result(timeout=20))) == [
            "accepted", "denied",
        ]
    with sessions() as db:
        rows = db.scalars(select(AIQuotaReservationRecord).where(
            AIQuotaReservationRecord.tenant_id == "tenant-budget-ci",
        )).all()
        assert len(rows) == 2
        assert {item.capability for item in rows} == {
            "ai.requests", "ai.total_tokens",
        }
        assert len({item.request_id for item in rows}) == 1
