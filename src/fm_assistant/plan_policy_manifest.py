"""Canonical plan quota snapshot derived from a licensed Assistant tenant.

This is a read-only projection. Core must receive it only over a separately
authenticated service channel with revocation/freshness checks before use.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db import PlanLimitORM
from .plan_limits import PlanLimitDenied, PlanLimitResolver


@dataclass(frozen=True, kw_only=True)
class PlanQuotaGrant:
    resource: str
    scope: str
    limit_units: int
    window_seconds: int


@dataclass(frozen=True, kw_only=True)
class LicensedQuotaManifest:
    tenant_id: str
    unit_id: str
    plan_code: str
    revision: int
    licensed_until: datetime
    grants: tuple[PlanQuotaGrant, ...]

    def policy_fingerprint(self) -> tuple:
        return (
            self.plan_code, self.revision,
            tuple((x.resource, x.scope, x.limit_units, x.window_seconds)
                  for x in self.grants),
        )


class LicensedQuotaManifestService:
    """Fail closed when plan/license, grants or scope is inconsistent."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions
        self._resolver = PlanLimitResolver(sessions)

    def resolve(
        self, *, tenant_id: str, unit_id: str, now: datetime,
    ) -> LicensedQuotaManifest:
        ref = self._resolver.resolve(
            tenant_id=tenant_id, unit_id=unit_id,
            resource="ai.requests", now=now,
        )
        token_ref = self._resolver.resolve(
            tenant_id=tenant_id, unit_id=unit_id,
            resource="ai.total_tokens", now=now,
        )
        if (ref.plan_code, ref.revision, ref.licensed_until) != (
            token_ref.plan_code, token_ref.revision, token_ref.licensed_until,
        ):
            raise PlanLimitDenied("plan.mixed_authority")
        with self._sessions() as db:
            records = db.scalars(
                select(PlanLimitORM).where(
                    PlanLimitORM.plan_code == ref.plan_code,
                    PlanLimitORM.revision == ref.revision,
                ).order_by(PlanLimitORM.resource),
            ).all()
            grants = tuple(PlanQuotaGrant(
                resource=record.resource, scope=record.scope,
                limit_units=record.limit_units,
                window_seconds=record.window_seconds,
            ) for record in records)
        if (
            len(grants) < 2
            or not {"ai.requests", "ai.total_tokens"}.issubset(
                {grant.resource for grant in grants}
            )
            or any(
                grant.scope not in {"tenant", "unit"}
                or grant.limit_units <= 0 or grant.window_seconds <= 0
                for grant in grants
            )
        ):
            raise PlanLimitDenied("plan.grants_incomplete")
        return LicensedQuotaManifest(
            tenant_id=tenant_id, unit_id=unit_id,
            plan_code=ref.plan_code, revision=ref.revision,
            licensed_until=ref.licensed_until, grants=grants,
        )
