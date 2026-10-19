"""F3.8 transactional quota reservations, not yet connected to provider calls.

Quota policies are provisioned by a separate authorized control plane.
The policy row is locked before every reserve/settle; this requires PostgreSQL
row-level locking in deployment. SQLite is used for sequential unit tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    func,
    select,
    text,
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
    period: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
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


@dataclass(frozen=True, kw_only=True)
class QuotaRequirement:
    """One plan metric bucket (scope key may represent an entire tenant)."""

    tenant_id: str
    unit_id: str
    capability: str
    units: int
    policy_revision: int | None = None


@dataclass(frozen=True, kw_only=True)
class QuotaUsageSnapshot:
    tenant_id: str
    unit_id: str
    capability: str
    limit_units: int
    window_seconds: int
    reserved_units: int
    consumed_units: int
    remaining_units: int
    period_ends_at: datetime
    policy_revision: int


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
        for_execution: bool = False,
    ) -> AIQuotaReservationRecord:
        scope = (tenant_id, unit_id, capability)
        if not all(_valid_id(i) for i in (*scope, request_id)) or len(capability) > 80:
            raise QuotaDenied("core_quota.invalid_scope")
        if type(for_execution) is not bool:
            raise QuotaDenied("core_quota.invalid_mode")
        if type(units) is not int or not 0 < units <= 2_000_000_000:
            raise QuotaDenied("core_quota.invalid_units")
        now = _utc(at)
        with self._sessions.begin() as db:
            policy = self._policy(db, scope)
            period = int(now.timestamp()) // policy.window_seconds
            key = (*scope, request_id)
            old = db.get(AIQuotaReservationRecord, key)
            if old is not None:
                if (
                    old.period != period
                    or old.reserved_units != units
                    or old.policy_revision != policy.revision
                ):
                    raise QuotaDenied("core_quota.request_conflict")
                # Accounting idempotency must never become a second provider call.
                if for_execution:
                    raise QuotaDenied("core_quota.execution_replay_denied")
                return old
            consumed = db.scalar(select(func.coalesce(func.sum(
                AIQuotaReservationRecord.reserved_units,
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

    def pending_for_reconciliation(
        self, *, tenant_id: str, unit_id: str, capability: str,
        older_than: datetime, limit: int = 100,
    ) -> tuple[AIQuotaReservationRecord, ...]:
        """Read-only scoped review of unresolved provider attempts.

        This never refunds or changes quota; only a separately authorized
        recovery workflow may resolve attempts with ambiguous outcomes.
        """
        if not all(_valid_id(v) for v in (tenant_id, unit_id, capability)):
            raise QuotaDenied("core_quota.invalid_scope")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise QuotaDenied("core_quota.invalid_limit")
        cutoff = _utc(older_than)
        with self._sessions() as db:
            records = db.scalars(
                select(AIQuotaReservationRecord).where(
                    AIQuotaReservationRecord.tenant_id == tenant_id,
                    AIQuotaReservationRecord.unit_id == unit_id,
                    AIQuotaReservationRecord.capability == capability,
                    AIQuotaReservationRecord.state == ReservationState.RESERVED,
                    AIQuotaReservationRecord.created_at < cutoff,
                ).order_by(
                    AIQuotaReservationRecord.created_at,
                    AIQuotaReservationRecord.request_id,
                ).limit(limit)
            ).all()
            return tuple(records)

    def project_signed_grants(
        self, *, tenant_id: str, unit_id: str, revision: int,
        grants: tuple[tuple[str, str, int, int], ...],
    ) -> None:
        """Version-fenced full projection from a verified Assistant license."""
        if (
            not _valid_id(tenant_id) or not _valid_id(unit_id)
            or type(revision) is not int or revision < 1
            or not 2 <= len(grants) <= 5
        ):
            raise QuotaDenied("core_quota.projection_invalid")
        items = sorted(grants)
        if (
            len({m for m, _, _, _ in items}) != len(items)
            or not {"ai.requests", "ai.total_tokens"}.issubset(
                {m for m, _, _, _ in items}
            )
            or any(
                m not in {"ai.requests", "ai.total_tokens",
                          "ai.input_tokens", "ai.output_tokens", "ai.cached_tokens"}
                or scope not in {"tenant", "unit"}
                or type(limit) is not int or not 0 < limit <= 2_000_000_000
                or type(window) is not int or not 0 < window <= 31_536_000
                for m, scope, limit, window in items
            )
        ):
            raise QuotaDenied("core_quota.projection_invalid")
        with self._sessions.begin() as db:
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                db.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:tenant), hashtext(:unit))"),
                    {"tenant": tenant_id, "unit": unit_id},
                )
            for metric, scope, limit, window in items:
                scoped_unit = "__tenant__" if scope == "tenant" else unit_id
                key = (tenant_id, scoped_unit, metric)
                record = db.get(AIQuotaPolicyRecord, key, with_for_update=True)
                if record is None:
                    db.add(AIQuotaPolicyRecord(
                        tenant_id=tenant_id, unit_id=scoped_unit,
                        capability=metric, limit_units=limit,
                        window_seconds=window, revision=revision,
                    ))
                    continue
                if record.revision > revision:
                    raise QuotaDenied("core_quota.projection_stale")
                if record.revision == revision:
                    if record.limit_units != limit or record.window_seconds != window:
                        raise QuotaDenied("core_quota.projection_conflict")
                    continue
                record.revision = revision
                record.limit_units = limit
                record.window_seconds = window
            db.flush()

    def reserve_bundle(
        self, *, needs: tuple[QuotaRequirement, ...],
        request_id: str, at: datetime,
    ) -> tuple[AIQuotaReservationRecord, ...]:
        """Atomically reserve every plan dimension or reject the whole request.

        PostgreSQL locks all policy rows in consistent sorted order. Scope keys
        (tenant-wide or unit-specific) must be derived by the trusted policy
        projector, never accepted from an untrusted client request.
        """
        if not needs or len(needs) > 32 or not _valid_id(request_id):
            raise QuotaDenied("core_quota.bundle_invalid")
        keys = [(v.tenant_id, v.unit_id, v.capability) for v in needs]
        if len(set(keys)) != len(keys) or len({x.tenant_id for x in needs}) != 1:
            raise QuotaDenied("core_quota.bundle_invalid")
        if any(
            not all(_valid_id(x) for x in key) or len(key[2]) > 80
            or type(need.units) is not int or not 0 < need.units <= 2_000_000_000
            or (need.policy_revision is not None and (
                type(need.policy_revision) is not int or need.policy_revision < 1
            ))
            for key, need in zip(keys, needs, strict=True)
        ):
            raise QuotaDenied("core_quota.bundle_invalid")
        now = _utc(at)
        ordered = sorted(needs, key=lambda item: (
            item.tenant_id, item.unit_id, item.capability,
        ))
        with self._sessions.begin() as db:
            staged = []
            for need in ordered:
                scope = (need.tenant_id, need.unit_id, need.capability)
                policy = self._policy(db, scope)
                if (need.policy_revision is not None
                        and policy.revision != need.policy_revision):
                    raise QuotaDenied("core_quota.policy_revision_mismatch")
                period = int(now.timestamp()) // policy.window_seconds
                if db.get(AIQuotaReservationRecord, (*scope, request_id)) is not None:
                    raise QuotaDenied("core_quota.execution_replay_denied")
                pending = db.scalar(select(func.coalesce(func.sum(
                    AIQuotaReservationRecord.reserved_units,
                ), 0)).where(
                    AIQuotaReservationRecord.tenant_id == need.tenant_id,
                    AIQuotaReservationRecord.unit_id == need.unit_id,
                    AIQuotaReservationRecord.capability == need.capability,
                    AIQuotaReservationRecord.period == period,
                    AIQuotaReservationRecord.state == ReservationState.RESERVED,
                ))
                spent = db.scalar(select(func.coalesce(func.sum(
                    AIQuotaReservationRecord.consumed_units,
                ), 0)).where(
                    AIQuotaReservationRecord.tenant_id == need.tenant_id,
                    AIQuotaReservationRecord.unit_id == need.unit_id,
                    AIQuotaReservationRecord.capability == need.capability,
                    AIQuotaReservationRecord.period == period,
                    AIQuotaReservationRecord.state == ReservationState.SETTLED,
                ))
                if int(pending) + int(spent) + need.units > policy.limit_units:
                    raise QuotaDenied("core_quota.limit_exceeded")
                staged.append(AIQuotaReservationRecord(
                    tenant_id=need.tenant_id,
                    unit_id=need.unit_id,
                    capability=need.capability,
                    request_id=request_id,
                    period=period,
                    policy_revision=policy.revision,
                    reserved_units=need.units,
                    consumed_units=0,
                    state=ReservationState.RESERVED,
                    created_at=now,
                ))
            db.add_all(staged)
            db.flush()
            return tuple(staged)

    def settle_bundle(
        self, *, usage: tuple[QuotaRequirement, ...], request_id: str,
    ) -> None:
        """Settle only confirmed metrics, retaining all reserves on failure."""
        if not usage or len(usage) > 32 or not _valid_id(request_id):
            raise QuotaDenied("core_quota.bundle_invalid")
        keys = [(x.tenant_id, x.unit_id, x.capability) for x in usage]
        if len(keys) != len(set(keys)) or len({x.tenant_id for x in usage}) != 1:
            raise QuotaDenied("core_quota.bundle_invalid")
        if any(
            not all(_valid_id(z) for z in key) or len(key[2]) > 80
            or type(item.units) is not int or item.units < 0
            or (item.policy_revision is not None and (
                type(item.policy_revision) is not int or item.policy_revision < 1
            ))
            for key, item in zip(keys, usage, strict=True)
        ):
            raise QuotaDenied("core_quota.bundle_invalid")
        with self._sessions.begin() as db:
            to_settle = []
            for item in sorted(usage, key=lambda x: (
                x.tenant_id, x.unit_id, x.capability,
            )):
                key = (item.tenant_id, item.unit_id, item.capability)
                policy = self._policy(db, key)
                if (item.policy_revision is not None
                        and policy.revision != item.policy_revision):
                    raise QuotaDenied("core_quota.policy_revision_mismatch")
                row = db.get(AIQuotaReservationRecord, (*key, request_id))
                if (row is not None and item.policy_revision is not None
                        and row.policy_revision != item.policy_revision):
                    raise QuotaDenied("core_quota.policy_revision_mismatch")
                if row is None or row.reserved_units < item.units:
                    raise QuotaDenied("core_quota.reservation_unavailable")
                if row.state == ReservationState.SETTLED:
                    if row.consumed_units != item.units:
                        raise QuotaDenied("core_quota.settlement_conflict")
                else:
                    to_settle.append((row, item.units))
            for row, consumed in to_settle:
                row.state = ReservationState.SETTLED
                row.consumed_units = consumed
            db.flush()

    def usage_snapshot(
        self, *, tenant_id: str, unit_id: str,
        capability: str, at: datetime,
    ) -> QuotaUsageSnapshot:
        """Scoped, read-only plan usage for alerts and commercial dashboards."""
        scope = (tenant_id, unit_id, capability)
        if not all(_valid_id(k) for k in scope) or len(capability) > 80:
            raise QuotaDenied("core_quota.invalid_scope")
        now = _utc(at)
        with self._sessions() as db:
            policy = self._policy(db, scope)
            period = int(now.timestamp()) // policy.window_seconds
            rows = db.scalars(select(AIQuotaReservationRecord).where(
                AIQuotaReservationRecord.tenant_id == tenant_id,
                AIQuotaReservationRecord.unit_id == unit_id,
                AIQuotaReservationRecord.capability == capability,
                AIQuotaReservationRecord.period == period,
            )).all()
            reserved = sum(
                row.reserved_units for row in rows
                if row.state == ReservationState.RESERVED
            )
            spent = sum(
                row.consumed_units for row in rows
                if row.state == ReservationState.SETTLED
            )
            return QuotaUsageSnapshot(
                tenant_id=tenant_id, unit_id=unit_id, capability=capability,
                limit_units=policy.limit_units, window_seconds=policy.window_seconds,
                reserved_units=reserved,
                consumed_units=spent,
                remaining_units=max(0, policy.limit_units - reserved - spent),
                period_ends_at=datetime.fromtimestamp(
                    period * policy.window_seconds, tz=UTC,
                ) + timedelta(seconds=policy.window_seconds),
                policy_revision=policy.revision,
            )
