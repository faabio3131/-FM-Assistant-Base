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
from core.ai_quota_store import (
    AIQuotaPolicyRecord,
    AIQuotaReservationRecord,
    QuotaDenied,
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
