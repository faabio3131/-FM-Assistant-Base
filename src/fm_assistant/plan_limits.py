"""Commercial plan allowances resolved exclusively from Assistant license authority.

No default unlimited AI quota. This read path is deliberately independent of
AI providers, payment gateways and prices; only versioned internal plan data.
Plan catalog writes are owned by the FM platform and never exposed through a
tenant self-service endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from .db import (
    PlanLimitORM,
    PlanVersionORM,
    TenantLicenseORM,
    TenantORM,
    UnitORM,
)


class PlanLimitDenied(PermissionError):
    """Fail-closed denial without leaking another tenant's plan."""


@dataclass(frozen=True, kw_only=True)
class ResolvedPlanLimit:
    tenant_id: str
    unit_id: str
    plan_code: str
    revision: int
    resource: str
    scope: str
    limit_units: int
    window_seconds: int
    licensed_until: datetime

    def __post_init__(self) -> None:
        if self.scope not in {"unit", "tenant"}:
            raise ValueError("plan.limit_scope_invalid")
        if self.revision <= 0 or self.limit_units <= 0 or self.window_seconds <= 0:
            raise ValueError("plan.limit_invalid")


class PlanLimitResolver:
    """A governed read port; callers MUST authenticate request tenant/unit."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def resolve(
        self, *, tenant_id: str, unit_id: str,
        resource: str, now: datetime,
    ) -> ResolvedPlanLimit:
        if (
            not all(isinstance(s, str) and 0 < len(s) <= 128 and s.strip() == s
                    for s in (tenant_id, unit_id, resource))
            or len(resource) > 80
            or not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise PlanLimitDenied("plan.limit_unavailable")
        timestamp = now.astimezone(UTC)
        with self._sessions() as db:
            tenant = db.get(TenantORM, tenant_id)
            unit = db.get(UnitORM, (tenant_id, unit_id))
            license_row = db.get(TenantLicenseORM, tenant_id)
            if (
                tenant is None or tenant.status != "active"
                or unit is None or unit.status != "active"
                or license_row is None
                or license_row.status not in {"active", "trial"}
                or license_row.plan_revision is None
                or license_row.plan_revision < 1
            ):
                raise PlanLimitDenied("plan.limit_unavailable")
            if license_row.status == "trial":
                cutoff = license_row.trial_ends_at
            else:
                cutoff = license_row.period_ends_at
            if cutoff is None:
                raise PlanLimitDenied("plan.period_unavailable")
            if cutoff.tzinfo is None:
                # SQLAlchemy+SQLite stores naive UTC, production timestamptz aware.
                cutoff = cutoff.replace(tzinfo=UTC)
            cutoff = cutoff.astimezone(UTC)
            if timestamp >= cutoff:
                raise PlanLimitDenied("plan.period_expired")
            key = (license_row.plan_code, license_row.plan_revision)
            version = db.get(PlanVersionORM, key)
            item = db.get(PlanLimitORM, (*key, resource))
            if version is None or version.status not in {"published", "retired"}:
                raise PlanLimitDenied("plan.limit_unavailable")
            if item is None or item.limit_units <= 0 or item.window_seconds <= 0:
                raise PlanLimitDenied("plan.limit_unavailable")
            return ResolvedPlanLimit(
                tenant_id=tenant_id, unit_id=unit_id,
                plan_code=key[0], revision=key[1],
                resource=resource, scope=item.scope,
                limit_units=item.limit_units,
                window_seconds=item.window_seconds,
                licensed_until=cutoff,
            )
