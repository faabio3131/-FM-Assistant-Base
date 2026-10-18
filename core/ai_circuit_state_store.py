"""PostgreSQL-serialized circuit admission, fencing and outcome handling.

Independent of provider adapters; activation requires a governed policy and
an explicitly injected store. Never stores provider secrets or request content.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from core.ai_circuit_breaker import (
    CircuitDenied,
    CircuitOutcome,
    CircuitPhase,
    CircuitPolicy,
    CircuitState,
    admit,
    aware,
    expire_probe,
    settle,
)
from core.ai_control_plane import ControlPlaneBase


class ProviderCircuitRecord(ControlPlaneBase):
    __tablename__ = "core_ai_provider_circuit_state"

    provider_id: Mapped[str] = mapped_column(
        ForeignKey("core_ai_providers.provider_id"), primary_key=True,
    )
    phase: Mapped[str] = mapped_column(String(12), nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False)
    until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    probe_id: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class PersistentCircuit:
    """One row lock serializes admissions/settlements for a provider.

    Fencing is enforced by the unguessable probe ID plus an immutable epoch.
    All methods fail closed when policy/record is missing.
    """

    def __init__(self, sessions: sessionmaker[Session], policy: CircuitPolicy):
        self._sessions = sessions
        self._policy = policy

    def _locked(self, db: Session, provider_id: str) -> ProviderCircuitRecord:
        if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 128:
            raise CircuitDenied("circuit.invalid_provider")
        record = db.scalar(
            select(ProviderCircuitRecord)
            .where(ProviderCircuitRecord.provider_id == provider_id)
            .with_for_update()
        )
        if record is None:
            raise CircuitDenied("circuit.unconfigured")
        return record

    @staticmethod
    def _state(record: ProviderCircuitRecord) -> CircuitState:
        until = record.until
        if until is not None and until.tzinfo is None:
            # PostgreSQL timestamptz returns aware; SQLite unit tests may not.
            until = until.replace(tzinfo=UTC)
        return CircuitState(
            phase=CircuitPhase(record.phase),
            failures=record.failures,
            until=until,
            probe_id=record.probe_id,
        )

    @staticmethod
    def _write(record: ProviderCircuitRecord, state: CircuitState) -> None:
        record.phase = state.phase.value
        record.failures = state.failures
        record.until = state.until
        record.probe_id = state.probe_id
        record.version += 1

    def claim(self, *, provider_id: str, now: datetime) -> tuple[str | None, int]:
        """Atomically claim one half-open probe or permit a CLOSED call."""
        now = aware(now)
        with self._sessions.begin() as db:
            record = self._locked(db, provider_id)
            old = self._state(record)
            token = uuid4().hex if old.phase is CircuitPhase.OPEN else None
            next_state, token = admit(old, self._policy, now=now, probe_id=token)
            if next_state != old:
                self._write(record, next_state)
                db.flush()
            return token, record.version

    def finish(
        self, *, provider_id: str, now: datetime, outcome: CircuitOutcome,
        probe_id: str | None, version: int,
    ) -> None:
        """Reject stale results from an earlier probe, even after lease reuse."""
        now = aware(now)
        if type(version) is not int or version < 0:
            raise CircuitDenied("circuit.invalid_fence")
        with self._sessions.begin() as db:
            record = self._locked(db, provider_id)
            old = self._state(record)
            if probe_id is not None and version != record.version:
                raise CircuitDenied("circuit.stale_fence")
            new = settle(old, self._policy, now=now, outcome=outcome, probe_id=probe_id)
            self._write(record, new)

    def recover_expired(self, *, provider_id: str, now: datetime) -> None:
        """Reopen an expired probe with a fresh cooldown, without new traffic."""
        now = aware(now)
        with self._sessions.begin() as db:
            record = self._locked(db, provider_id)
            next_state = expire_probe(self._state(record), self._policy, now=now)
            self._write(record, next_state)
