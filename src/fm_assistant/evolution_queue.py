"""Persistent encrypted FM Evolution inbound queue.

One worker claims each job before invoking AI. On crash or ambiguous outcome,
quarantine instead of replay to prevent duplicate model charges and messages.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from .credential_vault import CredentialVault
from .db import EvolutionInboundJobORM


@dataclass(frozen=True, kw_only=True)
class QueuedInbound:
    connection_id: str
    message_id: str
    sender: str
    text: str


class EvolutionInboundQueue:
    def __init__(self, sessions, vault: CredentialVault):
        self._sessions = sessions
        self._vault = vault

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
