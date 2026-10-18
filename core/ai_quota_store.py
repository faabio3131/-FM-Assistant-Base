"""F3.8 transactional quota reservations, not yet connected to provider calls.

Quota policies are provisioned by a separate authorized control plane.
The policy row is locked before every reserve/settle; this requires PostgreSQL
row-level locking in deployment. SQLite is used for sequential unit tests.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, func, select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from core.ai_control_plane import ControlPlaneBase


class QuotaDenied(ValueError):
    pass


class ReservationState(StrEnum):
    RESERVED = "reserved"
    SETTLED = "settled"


class AIQuotaPolicyRecord(ControlPlaneBase):
    __tablename__ = "core_ai_quota_policies"
    __table_args__ = (
        CheckConstraint("limit_units > 0", name="ck_ai_quota_positive_limit"),
        CheckConstraint("window_seconds > 0", name="ck_ai_quota_positive_window"),
    )

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    capability: Mapped[str] = mapped_column(String(80), primary_key=True)
    limit_units: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)


class AIQuotaReservationRecord(ControlPlaneBase):
    __tablename__ = "core_ai_quota_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "unit_id", "capability"],
            ["core_ai_quota_policies.tenant_id", "core_ai_quota_policies.unit_id",
             "core_ai_quota_policies.capability"],
        ),
        CheckConstraint("reserved_units > 0", name="ck_ai_quota_reserved_positive"),
        CheckConstraint("consumed_units >= 0", name="ck_ai_quota_consumed_nonnegative"),
    )

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    capability: Mapped[str] = mapped_column(String(80), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    period: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_units: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _valid_id(s: str) -> bool:
    return isinstance(s, str) and bool(s) and len(s) <= 128 and s.isascii() and all(
        c.isalnum() or c in "_.-" for c in s
    )


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise QuotaDenied("core_quota.time_invalid")
    return value.astimezone(UTC)


class QuotaReservations:
    """Fail-closed, single-policy-serialized reservation ledger."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    @staticmethod
    def _policy(db: Session, scope: tuple[str, str, str]) -> AIQuotaPolicyRecord:
        policy = db.scalar(
            select(AIQuotaPolicyRecord).where(
                AIQuotaPolicyRecord.tenant_id == scope[0],
                AIQuotaPolicyRecord.unit_id == scope[1],
                AIQuotaPolicyRecord.capability == scope[2],
            ).with_for_update()
        )
        if policy is None or policy.limit_units <= 0 or policy.window_seconds <= 0:
            raise QuotaDenied("core_quota.policy_unavailable")
        return policy

    def reserve(
        self, *, tenant_id: str, unit_id: str, capability: str,
        request_id: str, units: int, at: datetime,
    ) -> AIQuotaReservationRecord:
        scope = (tenant_id, unit_id, capability)
        if not all(_valid_id(i) for i in (*scope, request_id)):
            raise QuotaDenied("core_quota.invalid_scope")
        if type(units) is not int or not 0 < units <= 2_000_000_000:
            raise QuotaDenied("core_quota.invalid_units")
        now = _utc(at)
        with self._sessions.begin() as db:
            policy = self._policy(db, scope)
            period = int(now.timestamp()) // policy.window_seconds
            key = (*scope, request_id)
            old = db.get(AIQuotaReservationRecord, key)
            if old is not None:
                if old.period != period or old.reserved_units != units:
                    raise QuotaDenied("core_quota.request_conflict")
                return old
            consumed = db.scalar(select(func.coalesce(func.sum(
                AIQuotaReservationRecord.reserved_units -
                AIQuotaReservationRecord.consumed_units +
                AIQuotaReservationRecord.consumed_units,
            ), 0)).where(
                AIQuotaReservationRecord.tenant_id == tenant_id,
                AIQuotaReservationRecord.unit_id == unit_id,
                AIQuotaReservationRecord.capability == capability,
                AIQuotaReservationRecord.period == period,
                AIQuotaReservationRecord.state == ReservationState.RESERVED,
            ))
            settled = db.scalar(select(func.coalesce(func.sum(
                AIQuotaReservationRecord.consumed_units,
            ), 0)).where(
                AIQuotaReservationRecord.tenant_id == tenant_id,
                AIQuotaReservationRecord.unit_id == unit_id,
                AIQuotaReservationRecord.capability == capability,
                AIQuotaReservationRecord.period == period,
                AIQuotaReservationRecord.state == ReservationState.SETTLED,
            ))
            if int(consumed) + int(settled) + units > policy.limit_units:
                raise QuotaDenied("core_quota.limit_exceeded")
            item = AIQuotaReservationRecord(
                tenant_id=tenant_id, unit_id=unit_id, capability=capability,
                request_id=request_id, period=period, policy_revision=policy.revision,
                reserved_units=units, consumed_units=0,
                state=ReservationState.RESERVED, created_at=now,
            )
            db.add(item)
            db.flush()
            return item

    def settle(
        self, *, tenant_id: str, unit_id: str, capability: str,
        request_id: str, consumed_units: int,
    ) -> AIQuotaReservationRecord:
        scope = (tenant_id, unit_id, capability)
        if not all(_valid_id(i) for i in (*scope, request_id)):
            raise QuotaDenied("core_quota.invalid_scope")
        if type(consumed_units) is not int or consumed_units < 0:
            raise QuotaDenied("core_quota.invalid_units")
        with self._sessions.begin() as db:
            self._policy(db, scope)
            item = db.get(AIQuotaReservationRecord, (*scope, request_id))
            if item is None or consumed_units > item.reserved_units:
                raise QuotaDenied("core_quota.reservation_unavailable")
            if item.state == ReservationState.SETTLED:
                if item.consumed_units != consumed_units:
                    raise QuotaDenied("core_quota.settlement_conflict")
                return item
            item.consumed_units = consumed_units
            item.state = ReservationState.SETTLED
            db.flush()
            return item
