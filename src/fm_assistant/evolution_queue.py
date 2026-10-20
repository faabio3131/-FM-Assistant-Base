"""Persistent encrypted FM Evolution inbound queue.

One worker claims each job before invoking AI. On crash or ambiguous outcome,
quarantine instead of replay to prevent duplicate model charges and messages.
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError, OperationalError

from .credential_vault import CredentialVault
from .db import EvolutionInboundJobORM, IntegrationConnectionORM


class EvolutionQueueCapacityExceeded(RuntimeError):
    pass


@dataclass(frozen=True, kw_only=True)
class QueuedInbound:
    connection_id: str
    message_id: str
    sender: str
    text: str
    claim_generation: int = 1


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
                    sql_text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                    {"scope": "fm_evolution_queue:" + connection_id},
                )
            prior = session.get(EvolutionInboundJobORM, (connection_id, message_id))
            if prior is not None:
                return False
            pending = session.scalar(
                select(func.count()).select_from(EvolutionInboundJobORM).where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.state.in_(("pending", "processing", "sending")),
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
            generation = job.attempt_count + 1
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
                        updated_at=now, attempt_count=generation,
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
                claim_generation=generation,
            )

    def assert_claim_current(
        self, *, connection_id: str, message_id: str,
        max_age_seconds: int = 300, claim_generation: int | None = None,
    ) -> None:
        """Fail closed before external send if worker claim aged out or changed.

        This is an internal guard, NOT a replacement for network-level
        transaction fencing or a continuously renewed worker lease.
        """
        if type(max_age_seconds) is not int or not 60 <= max_age_seconds <= 86400:
            raise ValueError("evolution_claim_max_age_invalid")
        if claim_generation is not None and (type(claim_generation) is not int or claim_generation < 1):
            raise ValueError("evolution_claim_generation_invalid")
        cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        with self._sessions() as session:
            conditions = [
                EvolutionInboundJobORM.connection_id == connection_id,
                EvolutionInboundJobORM.message_id == message_id,
                EvolutionInboundJobORM.state.in_(("processing", "sending")),
                EvolutionInboundJobORM.claimed_at >= cutoff,
            ]
            if claim_generation is not None:
                conditions.append(EvolutionInboundJobORM.attempt_count == claim_generation)
            valid = session.scalar(
                select(func.count()).select_from(EvolutionInboundJobORM).where(*conditions)
            )
            if not valid:
                raise RuntimeError("evolution_claim_expired_or_revoked")

    def renew_claim(
        self, *, connection_id: str, message_id: str,
        claim_generation: int, max_age_seconds: int = 300,
    ) -> None:
        """Renew only the current, non-expired claim generation via atomic CAS.

        A crashed/expired or superseded worker cannot resurrect a lease.
        Renewal does not imply delivery authorization or provider-side fencing.
        """
        if type(claim_generation) is not int or claim_generation < 1:
            raise ValueError("evolution_claim_generation_invalid")
        if type(max_age_seconds) is not int or not 60 <= max_age_seconds <= 86400:
            raise ValueError("evolution_claim_max_age_invalid")
        now = datetime.now(UTC)
        with self._sessions() as session:
            result = session.execute(
                update(EvolutionInboundJobORM)
                .where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.message_id == message_id,
                    EvolutionInboundJobORM.state.in_(("processing", "sending")),
                    EvolutionInboundJobORM.attempt_count == claim_generation,
                    EvolutionInboundJobORM.claimed_at >= now - timedelta(seconds=max_age_seconds),
                )
                .values(claimed_at=now, updated_at=now)
            )
            if result.rowcount != 1:
                session.rollback()
                raise RuntimeError("evolution_claim_expired_or_revoked")
            session.commit()

    def finish(
        self, *, connection_id: str, message_id: str,
        reconciled: bool, code: str | None = None,
        claim_generation: int | None = None,
    ) -> None:
        if claim_generation is not None and (type(claim_generation) is not int or claim_generation < 1):
            raise ValueError("evolution_claim_generation_invalid")
        with self._sessions() as session:
            conditions = [
                EvolutionInboundJobORM.connection_id == connection_id,
                EvolutionInboundJobORM.message_id == message_id,
                EvolutionInboundJobORM.state.in_(("processing", "sending")),
            ]
            if claim_generation is not None:
                conditions.append(EvolutionInboundJobORM.attempt_count == claim_generation)
            # A network send can only be called complete with a persisted
            # provider acknowledgement; an unacknowledged send stays uncertain.
            if not reconciled:
                conditions.append(
                    (EvolutionInboundJobORM.state == "processing")
                    | (
                        (EvolutionInboundJobORM.state == "sending")
                        & (EvolutionInboundJobORM.outbound_status == "provider_acknowledged")
                    )
                )
            result = session.execute(
                update(EvolutionInboundJobORM)
                .where(*conditions)
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
                    EvolutionInboundJobORM.state.in_(("processing", "sending")),
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
                        EvolutionInboundJobORM.state.in_(("processing", "sending")),
                        EvolutionInboundJobORM.claimed_at < cutoff,
                    )
                    .execution_options(synchronize_session=False)
                    .values(state="reconcile_required", ciphertext="",
                            error_code="stale_processing", updated_at=now)
                )
                changed += result.rowcount
            session.commit()
            return changed


    @contextmanager
    def outbound_connection_guard(
        self, *, connection_id: str, expected_revision: int,
    ):
        """Serialize provider-send window with connection pause/revoke on PostgreSQL.

        A row lock is held through the bounded HTTP request. A pause/revocation
        acquiring this same row lock cannot complete while a send is in flight.
        Not a guarantee of provider delivery or cancellation of a started send.
        SQLite FOR UPDATE is a no-op; SQLite tests are functional, not a proof
        of distributed serialization.
        """
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("evolution_connection_revision_invalid")
        with self._sessions() as session:
            row = session.scalar(
                select(IntegrationConnectionORM)
                .where(IntegrationConnectionORM.connection_id == connection_id)
                .with_for_update()
            )
            if (
                row is None or row.provider_key != "whatsapp_evolution"
                or row.status != "active" or row.revision != expected_revision
            ):
                raise PermissionError("evolution_connection_changed_before_send")
            try:
                yield
            finally:
                # Release only after external request completes or throws.
                session.rollback()

    def begin_outbound(
        self, *, connection_id: str, message_id: str, claim_generation: int,
        max_age_seconds: int = 300,
    ) -> str:
        """Persist one send intent before HTTP; uncertain sends are not retried."""
        if type(claim_generation) is not int or claim_generation < 1:
            raise ValueError("evolution_claim_generation_invalid")
        if type(max_age_seconds) is not int or not 60 <= max_age_seconds <= 86400:
            raise ValueError("evolution_claim_max_age_invalid")
        now = datetime.now(UTC)
        operation_id = uuid.uuid4().hex
        with self._sessions() as session:
            result = session.execute(
                update(EvolutionInboundJobORM).where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.message_id == message_id,
                    EvolutionInboundJobORM.state == "processing",
                    EvolutionInboundJobORM.attempt_count == claim_generation,
                    EvolutionInboundJobORM.claimed_at >= now - timedelta(seconds=max_age_seconds),
                    EvolutionInboundJobORM.outbound_operation_id.is_(None),
                ).values(
                    state="sending", outbound_operation_id=operation_id,
                    outbound_status="uncertain", send_started_at=now, updated_at=now,
                )
            )
            if result.rowcount != 1:
                session.rollback()
                raise RuntimeError("evolution_outbound_intent_conflict")
            session.commit()
        return operation_id

    def record_outbound_result(
        self, *, connection_id: str, message_id: str, claim_generation: int,
        operation_id: str, outbound_reference: str,
    ) -> None:
        """Persist provider receipt for later reconciliation."""
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("evolution_outbound_operation_invalid")
        if not isinstance(outbound_reference, str) or not 0 < len(outbound_reference) <= 160:
            raise ValueError("evolution_outbound_reference_invalid")
        with self._sessions() as session:
            result = session.execute(
                update(EvolutionInboundJobORM).where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.message_id == message_id,
                    EvolutionInboundJobORM.state == "sending",
                    EvolutionInboundJobORM.attempt_count == claim_generation,
                    EvolutionInboundJobORM.outbound_operation_id == operation_id,
                ).values(
                    outbound_status="provider_acknowledged",
                    outbound_reference=outbound_reference,
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                session.rollback()
                raise RuntimeError("evolution_outbound_result_conflict")
            session.commit()

    def correlate_delivery_status(
        self, *, connection_id: str, outbound_reference: str,
        status: str, evidence_sha256: str,
    ) -> bool:
        """Only an authenticated upstream callback may supply evidence_sha256.

        Match an existing provider receipt within this exact connection. Do not
        create a mapping for unknown receipts or mistake a sent ACK for delivery.
        Monotonic rank prevents late updates from undoing a confirmed state.
        """
        import re

        ranks = {"sent": 1, "delivered": 2, "read": 3}
        if status not in ranks:
            raise ValueError("evolution_delivery_status_invalid")
        if (
            not isinstance(outbound_reference, str)
            or not 1 <= len(outbound_reference) <= 160
            or not isinstance(evidence_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None
        ):
            raise ValueError("evolution_delivery_evidence_invalid")
        with self._sessions() as session:
            matches = session.scalars(
                select(EvolutionInboundJobORM).where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.outbound_reference == outbound_reference,
                    EvolutionInboundJobORM.outbound_status == "provider_acknowledged",
                    EvolutionInboundJobORM.state.in_((
                        "complete", "reconcile_required", "reviewed", "sending",
                    )),
                ).with_for_update()
            ).all()
            # Unmatched or ambiguous references fail closed; never link by
            # phone, message text, time proximity or another tenant's ID.
            if len(matches) != 1:
                return False
            job = matches[0]
            prior_rank = ranks.get(job.delivery_status, 0)
            if ranks[status] <= prior_rank:
                return False
            job.delivery_status = status
            job.delivery_evidence_sha256 = evidence_sha256
            job.delivery_observed_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            session.commit()
            return True

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
            recent = session.scalars(
                select(EvolutionInboundJobORM)
                .where(EvolutionInboundJobORM.connection_id == connection_id)
                .order_by(EvolutionInboundJobORM.updated_at.desc(),
                          EvolutionInboundJobORM.message_id)
                .limit(limit)
            ).all()
            oldest = session.execute(
                select(
                    EvolutionInboundJobORM.state,
                    func.min(EvolutionInboundJobORM.created_at),
                )
                .where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.state.in_(("pending", "processing", "sending")),
                )
                .group_by(EvolutionInboundJobORM.state)
            ).all()
            now = datetime.now(UTC)
            ages = {}
            for state, timestamp in oldest:
                if timestamp is not None:
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=UTC)
                    ages[state] = max(0, int((now - timestamp).total_seconds()))
            return {
                "counts": {state: total for state, total in counts},
                "oldest_age_seconds": ages,
                "capacity": self._max_pending,
                "lifecycle": [
                    {
                        "message_id": row.message_id,
                        "state": row.state,
                        "attempt_count": row.attempt_count,
                        "received_at": row.created_at.isoformat(),
                        "claimed_at": row.claimed_at.isoformat() if row.claimed_at else None,
                        "send_started_at": (
                            row.send_started_at.isoformat() if row.send_started_at else None
                        ),
                        "last_transition_at": row.updated_at.isoformat(),
                        "outbound_status": row.outbound_status,
                        "outbound_operation_id": row.outbound_operation_id,
                        "outbound_reference": row.outbound_reference,
                        "evidence_candidate_reference": row.evidence_candidate_reference,
                        "evidence_candidate_digest": row.evidence_candidate_digest,
                        "evidence_candidate_only": row.evidence_candidate_reference is not None,
                        "delivery_status": row.delivery_status,
                        "delivery_evidence_sha256": row.delivery_evidence_sha256,
                        "delivery_observed_at": (
                            row.delivery_observed_at.isoformat()
                            if row.delivery_observed_at else None
                        ),
                        "requires_review": row.state == "reconcile_required",
                        "provider_delivery_confirmed": False,
                    }
                    for row in recent
                ],
                "reconciliation": [
                    {
                        "message_id": row.message_id,
                        "error_code": row.error_code,
                        "attempt_count": row.attempt_count,
                        "outbound_status": row.outbound_status,
                        "outbound_operation_id": row.outbound_operation_id,
                        "outbound_reference": row.outbound_reference,
                        "evidence_candidate_reference": row.evidence_candidate_reference,
                        "evidence_candidate_digest": row.evidence_candidate_digest,
                        "evidence_candidate_only": row.evidence_candidate_reference is not None,
                        "delivery_status": row.delivery_status,
                        "delivery_evidence_sha256": row.delivery_evidence_sha256,
                        "delivery_observed_at": (
                            row.delivery_observed_at.isoformat()
                            if row.delivery_observed_at else None
                        ),
                        "updated_at": row.updated_at.isoformat(),
                    }
                    for row in jobs
                ],
            }

    def can_investigate_missing_reference(
        self, *, connection_id: str, message_id: str, operation_id: str,
    ) -> bool:
        """Never query the provider for an arbitrary tenant-controlled reference."""
        with self._sessions() as session:
            return bool(session.scalar(
                select(func.count()).select_from(EvolutionInboundJobORM).where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.message_id == message_id,
                    EvolutionInboundJobORM.outbound_operation_id == operation_id,
                    EvolutionInboundJobORM.state == "reconcile_required",
                    EvolutionInboundJobORM.outbound_reference.is_(None),
                    EvolutionInboundJobORM.evidence_candidate_reference.is_(None),
                )
            ))

    def stage_provider_evidence_candidate(
        self, *, connection_id: str, message_id: str, operation_id: str,
        provider_reference: str, evidence_digest: str,
    ) -> bool:
        """Store read-only provider lookup evidence without clearing quarantine.

        An external provider record alone cannot establish that an ambiguous
        HTTP attempt created that record. It is a lead for governed review,
        never conclusive linking proof or a refund/automatic resend trigger.
        """
        import re

        if (
            not isinstance(operation_id, str)
            or re.fullmatch(r"[0-9a-f]{32}", operation_id) is None
            or not isinstance(provider_reference, str)
            or re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", provider_reference) is None
            or not isinstance(evidence_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence_digest) is None
        ):
            raise ValueError("evolution_evidence_candidate_invalid")
        with self._sessions() as session:
            result = session.execute(
                update(EvolutionInboundJobORM).where(
                    EvolutionInboundJobORM.connection_id == connection_id,
                    EvolutionInboundJobORM.message_id == message_id,
                    EvolutionInboundJobORM.state == "reconcile_required",
                    EvolutionInboundJobORM.outbound_operation_id == operation_id,
                    EvolutionInboundJobORM.outbound_reference.is_(None),
                    EvolutionInboundJobORM.evidence_candidate_reference.is_(None),
                ).values(
                    evidence_candidate_reference=provider_reference,
                    evidence_candidate_digest=evidence_digest,
                    evidence_requested_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                session.rollback()
                return False
            session.commit()
            return True

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
                    # A potentially sent message cannot be administratively
                    # cleared on an unsupported assertion. It needs a scoped
                    # authenticated provider status receipt first.
                    (
                        EvolutionInboundJobORM.outbound_operation_id.is_(None)
                        | EvolutionInboundJobORM.delivery_evidence_sha256.is_not(None)
                    ),
                )
                .values(
                    state="reviewed", updated_at=datetime.now(UTC),
                )
            )
            session.commit()
            return result.rowcount == 1
