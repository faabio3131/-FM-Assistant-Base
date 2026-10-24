"""FM-signed emergency LICENSE SECURITY HOLD, not a financial cancellation.

One-way fail-closed transition to suspended. No renewal, refund, payment
mutation, proration, reactivation or remote authorization bypass.
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
    LicenseSecurityHoldAuditORM,
    PlanSyncNonceORM,
    TenantLicenseORM,
    TenantORM,
)

PATH = "/internal/v1/command/assistant-plans/security-hold"
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")
HEX = re.compile(r"^[0-9a-f]{64}$")


class LicenseSecurityHoldDenied(PermissionError):
    pass


class SignedLicenseSecurityHold:
    """Mutates ONLY Assistant current license state after FM human step-up.

    Caller (Command) must prove FM RBAC+fresh step-up before signing. Assistant
    independently verifies MAC, freshness, exact tenant/license state and
    operation ID uniqueness, all in one SQL transaction.
    """

    def __init__(
        self, *, sessions, signing_key: str | None, key_id: str | None,
        trusted_organization: str | None,
    ) -> None:
        self._sessions = sessions
        self._key = signing_key
        self._key_id = key_id
        self._organization = trusted_organization

    def suspend(
        self, *, raw_body: bytes, headers: dict[str, str | None],
        product_code: str, organization_id: str, tenant_id: str,
        actor_user_id: str, command_request_id: str, approved_at: int,
        step_up_at: int, plan_code: str, plan_revision: int,
        expected_valid_until: int, reason: str,
    ) -> str:
        now = datetime.now(UTC)
        epoch = int(now.timestamp())
        kid = headers.get("key_id") or ""
        ts = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        signature = headers.get("signature") or ""
        if (
            not self._key or len(self._key) < 32 or not self._key_id
            or not self._organization or organization_id != self._organization
            or product_code != "VENDEATENDEIA" or reason != "security_hold"
            or not KEY_ID.fullmatch(kid) or kid != self._key_id
            or not NONCE.fullmatch(nonce) or not HEX.fullmatch(signature)
            or len(raw_body) > 2048 or not ts.isascii()
            or not ts.isdecimal() or len(ts) != 10
            or abs(int(ts) - epoch) > 60
            or not all(
                isinstance(value, str) and IDENTITY.fullmatch(value)
                for value in (tenant_id, actor_user_id, command_request_id, plan_code)
            )
            or len(plan_code) > 120
            or type(plan_revision) is not int or plan_revision < 1
            or type(expected_valid_until) is not int or expected_valid_until <= epoch
            or type(approved_at) is not int or type(step_up_at) is not int
            or approved_at > epoch + 15 or epoch - approved_at > 300
            or step_up_at > epoch + 15 or epoch - step_up_at > 300
        ):
            raise LicenseSecurityHoldDenied("license.security_hold_denied")
        expected = sign_command_control(
            key=self._key, key_id=kid, timestamp=ts, nonce=nonce,
            body=raw_body, path=PATH,
        )
        if not hmac.compare_digest(expected, signature):
            raise LicenseSecurityHoldDenied("license.security_hold_denied")
        try:
            actual = json.loads(raw_body)
        except (UnicodeDecodeError, ValueError) as exc:
            raise LicenseSecurityHoldDenied("license.security_hold_denied") from exc
        if actual != {
            "product_code": product_code,
            "organization_id": organization_id,
            "tenant_id": tenant_id,
            "actor_user_id": actor_user_id,
            "command_request_id": command_request_id,
            "approved_at": approved_at,
            "step_up_at": step_up_at,
            "plan_code": plan_code,
            "plan_revision": plan_revision,
            "expected_valid_until": expected_valid_until,
            "reason": reason,
        }:
            raise LicenseSecurityHoldDenied("license.security_hold_denied")
        try:
            with self._sessions.begin() as db:
                # A unique network nonce is atomically consumed with the hold.
                db.add(PlanSyncNonceORM(key_id=kid, nonce=nonce, created_at=now))
                db.flush()
                tenant = db.get(TenantORM, tenant_id)
                row = db.scalar(select(TenantLicenseORM).where(
                    TenantLicenseORM.tenant_id == tenant_id,
                ).with_for_update())
                if tenant is None or tenant.status != "active" or row is None:
                    raise LicenseSecurityHoldDenied("license.security_hold_denied")
                cutoff = (
                    row.trial_ends_at if row.status == "trial"
                    else row.period_ends_at
                )
                if (
                    row.status not in {"active", "trial"}
                    or row.plan_code != plan_code
                    or row.plan_revision != plan_revision
                    or cutoff is None
                ):
                    raise LicenseSecurityHoldDenied("license.security_hold_denied")
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=UTC)
                if int(cutoff.timestamp()) != expected_valid_until or cutoff <= now:
                    raise LicenseSecurityHoldDenied("license.security_hold_denied")
                old_status = row.status
                row.status = "suspended"
                row.updated_at = now
                db.add(LicenseSecurityHoldAuditORM(
                    key_id=kid, nonce=nonce,
                    command_request_id=command_request_id,
                    tenant_id=tenant_id, actor_id=actor_user_id,
                    plan_code=plan_code, plan_revision=plan_revision,
                    old_status=old_status,
                    expected_valid_until=expected_valid_until,
                    held_at=now,
                ))
                db.flush()
                return "suspended"
        except IntegrityError as exc:
            raise LicenseSecurityHoldDenied("license.security_hold_denied") from exc
