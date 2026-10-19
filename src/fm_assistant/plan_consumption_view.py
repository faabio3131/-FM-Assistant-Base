"""Tenant-scoped, safe plan and usage view for customer dashboards.

No commercial prices or FM provider costs cross this customer boundary.
Metering is unavailable until the trusted Core transport is integrated;
unknown usage is never represented as zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db import PlanLimitORM, PlanVersionORM
from .plan_limits import PlanLimitResolver


@dataclass(frozen=True, kw_only=True)
class MeterReading:
    consumed_units: int
    reserved_units: int
    remaining_units: int
    observed_at: datetime
    policy_revision: int
    limit_units: int
    window_seconds: int

    def __post_init__(self) -> None:
        if (
            any(type(v) is not int or v < 0 for v in (
                self.consumed_units, self.reserved_units, self.remaining_units,
            ))
            or self.policy_revision < 1 or self.limit_units < 1
            or self.window_seconds < 1
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("plan.meter_reading_invalid")


class TrustedUsageReader(Protocol):
    def read(
        self, *, tenant_id: str, unit_id: str, metric: str,
        scope: str, at: datetime, policy_revision: int,
        limit_units: int, window_seconds: int,
    ) -> MeterReading | None: ...


class UnavailableUsageReader:
    def read(
        self, *, tenant_id: str, unit_id: str, metric: str,
        scope: str, at: datetime, policy_revision: int,
        limit_units: int, window_seconds: int,
    ) -> None:
        return None


# Provider costs remain confidential FM operational data, never client quota UI.
PRIVATE_METRICS = frozenset({"ai.cost_usd_microunits"})


class PlanConsumptionView:
    def __init__(
        self, sessions: sessionmaker[Session],
        *, reader: TrustedUsageReader | None = None,
    ) -> None:
        self._sessions = sessions
        self._resolver = PlanLimitResolver(sessions)
        self._reader = reader or UnavailableUsageReader()

    def get(self, *, tenant_id: str, unit_id: str, now: datetime) -> dict:
        # Mandatory plan/license check precedes any catalog, metering read,
        # and never accepts a tenant or unit from browser query/body data.
        ref = self._resolver.resolve(
            tenant_id=tenant_id, unit_id=unit_id,
            resource="ai.requests", now=now,
        )
        token_ref = self._resolver.resolve(
            tenant_id=tenant_id, unit_id=unit_id,
            resource="ai.total_tokens", now=now,
        )
        if (token_ref.plan_code, token_ref.revision) != (
            ref.plan_code, ref.revision,
        ):
            raise ValueError("plan.mixed_revision")
        with self._sessions() as session:
            version = session.get(PlanVersionORM, (ref.plan_code, ref.revision))
            limits = session.scalars(select(PlanLimitORM).where(
                PlanLimitORM.plan_code == ref.plan_code,
                PlanLimitORM.revision == ref.revision,
            ).order_by(PlanLimitORM.resource)).all()
            rows = [(x.resource, x.scope, x.limit_units, x.window_seconds)
                    for x in limits if x.resource not in PRIVATE_METRICS]
        counters = []
        for resource, scope, limit, period_seconds in rows:
            reading = self._reader.read(
                tenant_id=tenant_id, unit_id=unit_id,
                metric=resource, scope=scope, at=now,
                policy_revision=ref.revision,
                limit_units=limit, window_seconds=period_seconds,
            )
            # A mismatch is stale/unknown, never evidence of available credit.
            if reading is not None and (
                reading.policy_revision != ref.revision
                or reading.limit_units != limit
                or reading.window_seconds != period_seconds
                or reading.consumed_units + reading.reserved_units
                + reading.remaining_units != limit
            ):
                reading = None
            committed = (
                reading.consumed_units + reading.reserved_units
                if reading is not None else None
            )
            utilization = (
                (100 * committed // limit)
                if committed is not None and limit > 0 else None
            )
            warning_level = (
                "blocked" if utilization is not None and utilization >= 100
                else "critical" if utilization is not None and utilization >= 90
                else "warning" if utilization is not None and utilization >= 70
                else "normal" if utilization is not None
                else "unknown"
            )
            counters.append({
                "utilization_percent": utilization,
                "warning_level": warning_level,
                "committed_units": committed,
                "resource": resource,
                "scope": scope,
                "limit_units": limit,
                "window_seconds": period_seconds,
                "status": "observed" if reading else "metering_unavailable",
                "consumed_units": reading.consumed_units if reading else None,
                "reserved_units": reading.reserved_units if reading else None,
                "remaining_units": reading.remaining_units if reading else None,
                "observed_at": reading.observed_at.isoformat() if reading else None,
            })
        return {
            "plan_code": ref.plan_code, "revision": ref.revision,
            "plan_name": version.label if version else ref.plan_code,
            "licensed_until": ref.licensed_until.isoformat(),
            "all_features_included": True,
            "consumption": counters,
            "usage_verified": bool(counters) and all(
                item["status"] == "observed" for item in counters
            ),
        }
