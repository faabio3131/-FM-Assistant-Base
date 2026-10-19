"""Persistent encrypted FM Evolution inbound queue.

One worker claims each job before invoking AI. On crash or ambiguous outcome,
quarantine instead of replay to prevent duplicate model charges and messages.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from .credential_vault import CredentialVault
from .db import EvolutionInboundJobORM


class EvolutionQueueCapacityExceeded(RuntimeError):
    pass


@dataclass(frozen=True, kw_only=True)
class QueuedInbound:
    connection_id: str
    message_id: str
    sender: str
    text: str


class EvolutionInboundQueue:
    def __init__(
        self, sessions, vault: CredentialVault, *, max_pending_per_connection: int = 250,
    ):
        if type(max_pending_per_connection) is not int or not 1 <= max_pending_per_connection <= 10000:
            raise ValueError("evolution_queue_capacity_invalid")
        self._sessions = sessions
        self._vault = vault
        self._max_pending = max_pending_per_connection

    def enqueue(
        self, *, connection_id: str, message_id: str,
        sender: str, text: str,
    ) -> bool:
        """Persist encrypted payload atomically; reject duplicate message IDs."""
        cipher = self._vault.encrypt(json.dumps({
            "sender": sender, "text": text,
        }, separators=(",", ":"), ensure_ascii=False))
        now = datetime.now(UTC)
        with self._sessions() as session:
            # Serialize capacity check + insertion for PostgreSQL across all
            # API replicas. The unique PK independently enforces deduplication.
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                    {"scope": "fm_evolution_queue:" + connection_id},
                )
            prior = session.get(EvolutionInboundJobORM, (connection_id, message_id))
            if prior is not None:
                return False
            pending = session.scalar(
                select(func.count()).select_from(EvolutionInboundJobORM).where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.state.in_(("pending", "processing")),
                )
            )
            if int(pending or 0) >= self._max_pending:
                raise EvolutionQueueCapacityExceeded("evolution_queue_capacity_exceeded")
            session.add(EvolutionInboundJobORM(
                connection_id=connection_id, message_id=message_id,
                ciphertext=cipher, state="pending", attempt_count=0,
                created_at=now, updated_at=now, claimed_at=None, error_code=None,
            ))
            try:
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                return False

    def claim(self) -> QueuedInbound | None:
        """One atomic claim across workers (PG SKIP LOCKED, CAS on SQLite)."""
        with self._sessions() as session:
            stmt = (
                select(EvolutionInboundJobORM)
                .where(EvolutionInboundJobORM.state == "pending")
                .order_by(EvolutionInboundJobORM.created_at,
                          EvolutionInboundJobORM.connection_id,
                          EvolutionInboundJobORM.message_id)
                .limit(1)
            )
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            job = session.scalar(stmt)
            if job is None:
                return None
            now = datetime.now(UTC)
            try:
                result = session.execute(
                    update(EvolutionInboundJobORM)
                    .where(
                        EvolutionInboundJobORM.connection_id == job.connection_id,
                        EvolutionInboundJobORM.message_id == job.message_id,
                        EvolutionInboundJobORM.state == "pending",
                    )
                    .values(
                        state="processing", claimed_at=now,
                        updated_at=now, attempt_count=job.attempt_count + 1,
                    )
                )
                if result.rowcount != 1:
                    session.rollback()
                    return None
                session.commit()
            except OperationalError:
                # SQLite may detect competing snapshots as database-busy.
                # Never infer a successful claim or execute AI in that case.
                session.rollback()
                return None
            # Invalid ciphertext is quarantined rather than exposed or replayed.
            try:
                data = json.loads(self._vault.decrypt(job.ciphertext))
                sender, message = data["sender"], data["text"]
                if not isinstance(sender, str) or not isinstance(message, str):
                    raise TypeError("evolution_queued_payload_invalid")
            except (ValueError, KeyError, TypeError):
                self.finish(
                    connection_id=job.connection_id, message_id=job.message_id,
                    reconciled=True, code="encrypted_job_invalid",
                )
                return None
            return QueuedInbound(
                connection_id=job.connection_id, message_id=job.message_id,
                sender=sender, text=message,
            )

    def finish(
        self, *, connection_id: str, message_id: str,
        reconciled: bool, code: str | None = None,
    ) -> None:
        with self._sessions() as session:
            result = session.execute(
                update(EvolutionInboundJobORM)
                .where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.message_id == message_id,
                    EvolutionInboundJobORM.state == "processing",
                )
                .values(
                    state="reconcile_required" if reconciled else "complete",
                    ciphertext="", error_code=(code or "")[:160] if reconciled else None,
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                raise RuntimeError("evolution_job_state_conflict")
            session.commit()

    def quarantine_stale(self, *, older_than_seconds: int = 300, limit: int = 100) -> int:
        if type(older_than_seconds) is not int or not 60 <= older_than_seconds <= 86400:
            raise ValueError("evolution_queue_window_invalid")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("evolution_queue_limit_invalid")
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=older_than_seconds)
        with self._sessions() as session:
            stmt = (
                select(EvolutionInboundJobORM)
                .where(
                    EvolutionInboundJobORM.state == "processing",
                    EvolutionInboundJobORM.claimed_at < cutoff,
                )
                .order_by(EvolutionInboundJobORM.claimed_at)
                .limit(limit)
            )
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            jobs = session.scalars(stmt).all()
            changed = 0
            for job in jobs:
                result = session.execute(
                    update(EvolutionInboundJobORM)
                    .where(
                        EvolutionInboundJobORM.connection_id == job.connection_id,
                        EvolutionInboundJobORM.message_id == job.message_id,
                        EvolutionInboundJobORM.state == "processing",
                        EvolutionInboundJobORM.claimed_at < cutoff,
                    )
                    .execution_options(synchronize_session=False)
                    .values(state="reconcile_required", ciphertext="",
                            error_code="stale_processing", updated_at=now)
                )
                changed += result.rowcount
            session.commit()
            return changed

    def state(self, *, connection_id: str, message_id: str) -> str | None:
        with self._sessions() as session:
            row = session.get(EvolutionInboundJobORM, (connection_id, message_id))
            return row.state if row is not None else None

    def operational_snapshot(
        self, *, connection_id: str, limit: int = 50,
    ) -> dict:
        """No phone or message content; tenant scope verified by caller."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("evolution_queue_snapshot_limit_invalid")
        with self._sessions() as session:
            counts = session.execute(
                select(EvolutionInboundJobORM.state, func.count())
                .where(EvolutionInboundJobORM.connection_id == connection_id)
                .group_by(EvolutionInboundJobORM.state)
            ).all()
            jobs = session.scalars(
                select(EvolutionInboundJobORM)
                .where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.state == "reconcile_required",
                )
                .order_by(EvolutionInboundJobORM.updated_at.desc())
                .limit(limit)
            ).all()
            return {
                "counts": {state: total for state, total in counts},
                "capacity": self._max_pending,
                "reconciliation": [
                    {
                        "message_id": row.message_id,
                        "error_code": row.error_code,
                        "attempt_count": row.attempt_count,
                        "updated_at": row.updated_at.isoformat(),
                    }
                    for row in jobs
                ],
            }

    def acknowledge_reconciliation(
        self, *, connection_id: str, message_id: str,
    ) -> bool:
        """Operator acknowledgment, never automatic replay or deletion."""
        with self._sessions() as session:
            result = session.execute(
                update(EvolutionInboundJobORM)
                .where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.message_id == message_id,
                    EvolutionInboundJobORM.state == "reconcile_required",
                )
                .values(
                    state="reviewed", updated_at=datetime.now(UTC),
                )
            )
            session.commit()
            return result.rowcount == 1
