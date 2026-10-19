"""Corporate-signed tenant license binding to an immutable consumption plan.

Only links plan catalog revisions; never creates paid subscriptions or extends
trial/paid periods. Changing an existing revision requires the separate
governed upgrade/migration workflow.
"""
from __future__ import annotations

import hmac
import json
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .command_bridge_control_service import sign_command_control
from .db import (
    PlanBindingAuditORM,
    PlanLimitORM,
    PlanSyncNonceORM,
    PlanVersionORM,
    TenantLicenseORM,
    TenantORM,
)

BIND_PATH = "/internal/v1/command/assistant-plans/bind"
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")


class PlanLicenseBindingDenied(PermissionError):
    pass


class GovernedPlanLicenseBinding:
    def __init__(
        self, *, sessions, signing_key: str | None,
        key_id: str | None, trusted_organization: str | None,
    ) -> None:
        self._sessions = sessions
        self._key = signing_key
        self._key_id = key_id
        self._org = trusted_organization

    def bind(
        self, *, headers: dict[str, str | None], raw_body: bytes,
        product_code: str, organization_id: str,
        actor_user_id: str, approved_at: int, tenant_id: str,
        plan_code: str, plan_revision: int,
    ) -> str:
        now = datetime.now(UTC)
        ts = headers.get("timestamp") or ""
        kid = headers.get("key_id") or ""
        nonce = headers.get("nonce") or ""
        sig = headers.get("signature") or ""
        if (
            not self._key or len(self._key) < 32 or not self._key_id
            or not self._org or product_code != "VENDEATENDEIA"
            or organization_id != self._org or kid != self._key_id
            or len(raw_body) > 4096 or not NONCE.fullmatch(nonce)
            or len(ts) != 10 or not ts.isascii() or not ts.isdecimal()
            or abs(int(ts) - int(now.timestamp())) > 60
            or len(sig) != 64
            or any(
                not isinstance(s, str) or not IDENTIFIER.fullmatch(s)
                for s in (actor_user_id, tenant_id, plan_code)
            )
            or len(plan_code) > 120
            or type(plan_revision) is not int or plan_revision < 1
            or type(approved_at) is not int or approved_at > int(now.timestamp()) + 15
            or approved_at < int(now.timestamp()) - 366 * 86400
        ):
            raise PlanLicenseBindingDenied("plan.binding_denied")
        expected = sign_command_control(
            key=self._key, key_id=kid, timestamp=ts, nonce=nonce,
            body=raw_body, path=BIND_PATH,
        )
        if not hmac.compare_digest(expected, sig):
            raise PlanLicenseBindingDenied("plan.binding_denied")
        try:
            decoded = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PlanLicenseBindingDenied("plan.binding_denied") from exc
        if decoded != {
            "product_code": product_code,
            "organization_id": organization_id,
            "actor_user_id": actor_user_id,
            "approved_at": approved_at,
            "tenant_id": tenant_id,
            "plan_code": plan_code,
            "plan_revision": plan_revision,
        }:
            raise PlanLicenseBindingDenied("plan.binding_denied")

        try:
            with self._sessions.begin() as db:
                # Must be atomic with license and audit, even across workers.
                db.add(PlanSyncNonceORM(key_id=kid, nonce=nonce, created_at=now))
                db.flush()
                tenant = db.get(TenantORM, tenant_id)
                license_row = db.scalar(select(TenantLicenseORM).where(
                    TenantLicenseORM.tenant_id == tenant_id,
                ).with_for_update())
                version = db.get(PlanVersionORM, (plan_code, plan_revision))
                if (
                    tenant is None or tenant.status != "active"
                    or license_row is None or license_row.status not in {"active", "trial"}
                    or version is None or version.status != "published"
                ):
                    raise PlanLicenseBindingDenied("plan.binding_denied")
                cutoff = (
                    license_row.trial_ends_at if license_row.status == "trial"
                    else license_row.period_ends_at
                )
                if cutoff is None:
                    raise PlanLicenseBindingDenied("plan.binding_denied")
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=UTC)
                if cutoff.astimezone(UTC) <= now:
                    raise PlanLicenseBindingDenied("plan.binding_denied")
                metrics = set(db.scalars(select(PlanLimitORM.resource).where(
                    PlanLimitORM.plan_code == plan_code,
                    PlanLimitORM.revision == plan_revision,
                )).all())
                if not {"ai.requests", "ai.total_tokens"}.issubset(metrics):
                    raise PlanLicenseBindingDenied("plan.binding_denied")
                if license_row.plan_revision is not None:
                    if (
                        license_row.plan_code == plan_code
                        and license_row.plan_revision == plan_revision
                    ):
                        return "already_bound"
                    raise PlanLicenseBindingDenied("plan.transition_required")
                prior_code = license_row.plan_code
                license_row.plan_code = plan_code
                license_row.plan_revision = plan_revision
                license_row.updated_at = now
                db.add(PlanBindingAuditORM(
                    tenant_id=tenant_id, key_id=kid, nonce=nonce,
                    actor_id=actor_user_id, old_plan_code=prior_code,
                    plan_code=plan_code, plan_revision=plan_revision, bound_at=now,
                ))
                db.flush()
                return "bound"
        except IntegrityError as exc:
            raise PlanLicenseBindingDenied("plan.binding_denied") from exc
