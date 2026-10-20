"""Strict HMAC commercial license transitions from the FM corporate Command.

This is NOT the emergency security-hold path. A signed FM Command assertion
is an internal authority envelope, NOT independent proof from a PSP.
Unknown, stale or raced commands fail closed with no partial license writes.
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
    CommercialLicenseTransitionAuditORM,
    PlanLimitORM,
    PlanSyncNonceORM,
    PlanVersionORM,
    TenantLicenseORM,
    TenantORM,
)

PATH = "/internal/v1/command/assistant-plans/commercial-transition"
STATUS_PATH = "/internal/v1/command/assistant-plans/commercial-status"
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")
KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
ACTIONS = frozenset({
    "SUSPEND_DELINQUENCY",
    "REACTIVATE_VERIFIED",
    "RENEW_VERIFIED",
    "APPLY_UPGRADE",
    "APPLY_DOWNGRADE",
    "CANCEL_AT_PERIOD_END",
})
PAID_ACTIONS = frozenset({
    "REACTIVATE_VERIFIED", "RENEW_VERIFIED", "APPLY_UPGRADE",
    "APPLY_DOWNGRADE",
})


class CommercialLicenseTransitionDenied(PermissionError):
    pass


class SignedCommercialLicenseTransition:
    def __init__(
        self, *, sessions, signing_key: str | None,
        key_id: str | None, trusted_organization: str | None,
    ) -> None:
        self._sessions = sessions
        self._key = signing_key
        self._key_id = key_id
        self._organization = trusted_organization

    def read_status(
        self, *, headers: dict[str, str | None], raw_body: bytes,
        product_code: str, organization_id: str, tenant_id: str,
        command_request_id: str,
    ) -> dict[str, object]:
        """Authenticated read-only recovery snapshot for an uncertain FM op.

        The nonce is consumed to prevent replay, but the license is never
        mutated. No status from this path is proof of a PSP settlement.
        """
        now = datetime.now(UTC)
        stamp = int(now.timestamp())
        ts = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        kid = headers.get("key_id") or ""
        mac = headers.get("signature") or ""
        if (
            not self._key or len(self._key) < 32 or not self._key_id
            or not self._organization
            or product_code != "VENDEATENDEIA"
            or organization_id != self._organization
            or kid != self._key_id or not KEY_ID.fullmatch(kid)
            or not NONCE.fullmatch(nonce) or not HEX.fullmatch(mac)
            or not ts.isascii() or not ts.isdecimal() or len(ts) != 10
            or abs(int(ts)-stamp) > 60 or len(raw_body) > 1024
            or any(not isinstance(v, str) or not IDENTITY.fullmatch(v)
                   for v in (tenant_id, command_request_id))
        ):
            raise CommercialLicenseTransitionDenied("license.commercial_denied")
        expected = sign_command_control(
            key=self._key, key_id=kid, timestamp=ts, nonce=nonce,
            body=raw_body, path=STATUS_PATH,
        )
        if not hmac.compare_digest(expected, mac):
            raise CommercialLicenseTransitionDenied("license.commercial_denied")
        try:
            body = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise CommercialLicenseTransitionDenied("license.commercial_denied") from exc
        if body != {
            "product_code":product_code,"organization_id":organization_id,
            "tenant_id":tenant_id,"command_request_id":command_request_id,
        }:
            raise CommercialLicenseTransitionDenied("license.commercial_denied")
        try:
            with self._sessions.begin() as db:
                db.add(PlanSyncNonceORM(key_id=kid, nonce=nonce, created_at=now))
                db.flush()
                tenant = db.get(TenantORM, tenant_id)
                row = db.scalar(select(TenantLicenseORM).where(
                    TenantLicenseORM.tenant_id == tenant_id,
                ).with_for_update())
                if tenant is None or tenant.status != "active" or row is None:
                    raise CommercialLicenseTransitionDenied("license.commercial_denied")
                event = db.get(CommercialLicenseTransitionAuditORM,command_request_id)
                if event is not None and event.tenant_id != tenant_id:
                    raise CommercialLicenseTransitionDenied("license.commercial_denied")
                cutoff = row.trial_ends_at if row.status == "trial" else row.period_ends_at
                if cutoff is None:
                    raise CommercialLicenseTransitionDenied("license.commercial_denied")
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=UTC)
                return {
                    "operation_status":"applied" if event else "not_applied",
                    "applied_action":event.action if event else None,
                    "license_status":row.status,
                    "plan_code":row.plan_code,
                    "plan_revision":row.plan_revision,
                    "valid_until":int(cutoff.timestamp()),
                    "tenant_id":tenant_id,
                }
        except IntegrityError as exc:
            raise CommercialLicenseTransitionDenied("license.commercial_denied") from exc

    def apply(
        self, *, headers: dict[str, str | None], raw_body: bytes,
        product_code: str, organization_id: str, tenant_id: str,
        actor_user_id: str, command_request_id: str,
        approved_at: int, action: str, expected_status: str,
        expected_plan_code: str, expected_plan_revision: int,
        expected_valid_until: int, target_plan_code: str,
        target_plan_revision: int, target_valid_until: int,
        effective_at: int, verified_payment_ref: str,
    ) -> str:
        now = datetime.now(UTC)
        stamp = int(now.timestamp())
        ts = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        kid = headers.get("key_id") or ""
        mac = headers.get("signature") or ""
        identifiers = (
            tenant_id, actor_user_id, command_request_id,
            expected_plan_code, target_plan_code, verified_payment_ref,
        )
        if (
            not self._key or len(self._key) < 32
            or not self._key_id or not self._organization
            or product_code != "VENDEATENDEIA"
            or organization_id != self._organization
            or kid != self._key_id or not KEY_ID.fullmatch(kid)
            or not NONCE.fullmatch(nonce) or not HEX.fullmatch(mac)
            or len(raw_body) > 3072
            or not ts.isascii() or not ts.isdecimal() or len(ts) != 10
            or abs(int(ts) - stamp) > 60
            or action not in ACTIONS
            or expected_status not in {"active", "trial", "suspended"}
            or any(not isinstance(v, str) or not IDENTITY.fullmatch(v)
                   for v in identifiers)
            or len(expected_plan_code) > 120 or len(target_plan_code) > 120
            or type(expected_plan_revision) is not int
            or type(target_plan_revision) is not int
            or expected_plan_revision < 1 or target_plan_revision < 1
            or any(type(x) is not int for x in (
                approved_at, expected_valid_until, target_valid_until,
                effective_at,
            ))
            or approved_at > stamp + 15 or stamp - approved_at > 300
            or effective_at > stamp + 15
            or target_valid_until <= 0 or expected_valid_until <= 0
            or action in PAID_ACTIONS and (
                verified_payment_ref == "none"
                or len(verified_payment_ref) < 8
            )
            or action not in PAID_ACTIONS and verified_payment_ref != "none"
        ):
            raise CommercialLicenseTransitionDenied("license.commercial_denied")
        expected = sign_command_control(
            key=self._key, key_id=kid, timestamp=ts, nonce=nonce,
            body=raw_body, path=PATH,
        )
        if not hmac.compare_digest(expected, mac):
            raise CommercialLicenseTransitionDenied("license.commercial_denied")
        try:
            body = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise CommercialLicenseTransitionDenied(
                "license.commercial_denied",
            ) from exc
        if body != {
            "product_code": product_code,
            "organization_id": organization_id,
            "tenant_id": tenant_id,
            "actor_user_id": actor_user_id,
            "command_request_id": command_request_id,
            "approved_at": approved_at,
            "action": action,
            "expected_status": expected_status,
            "expected_plan_code": expected_plan_code,
            "expected_plan_revision": expected_plan_revision,
            "expected_valid_until": expected_valid_until,
            "target_plan_code": target_plan_code,
            "target_plan_revision": target_plan_revision,
            "target_valid_until": target_valid_until,
            "effective_at": effective_at,
            "verified_payment_ref": verified_payment_ref,
        }:
            raise CommercialLicenseTransitionDenied("license.commercial_denied")
        try:
            with self._sessions.begin() as db:
                db.add(PlanSyncNonceORM(
                    key_id=kid, nonce=nonce, created_at=now,
                ))
                db.flush()
                tenant = db.get(TenantORM, tenant_id)
                license_row = db.scalar(select(TenantLicenseORM).where(
                    TenantLicenseORM.tenant_id == tenant_id,
                ).with_for_update())
                if (
                    tenant is None or tenant.status != "active"
                    or license_row is None
                    or license_row.status != expected_status
                    or license_row.plan_code != expected_plan_code
                    or license_row.plan_revision != expected_plan_revision
                ):
                    raise CommercialLicenseTransitionDenied("license.commercial_denied")
                cutoff = (
                    license_row.trial_ends_at
                    if license_row.status == "trial" else
                    license_row.period_ends_at
                )
                if cutoff is None:
                    raise CommercialLicenseTransitionDenied("license.commercial_denied")
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=UTC)
                if int(cutoff.timestamp()) != expected_valid_until:
                    raise CommercialLicenseTransitionDenied("license.commercial_denied")
                if action in {"SUSPEND_DELINQUENCY", "CANCEL_AT_PERIOD_END"}:
                    if target_plan_code != expected_plan_code or (
                        target_plan_revision != expected_plan_revision
                        or target_valid_until != expected_valid_until
                    ):
                        raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    if action == "SUSPEND_DELINQUENCY":
                        if expected_status not in {"active", "trial"}:
                            raise CommercialLicenseTransitionDenied("license.commercial_denied")
                        result_status = "suspended"
                    else:
                        if stamp < expected_valid_until:
                            raise CommercialLicenseTransitionDenied("license.commercial_denied")
                        result_status = "cancelled"
                else:
                    if target_valid_until <= stamp:
                        raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    if action == "REACTIVATE_VERIFIED":
                        if expected_status != "suspended" or (
                            target_plan_code != expected_plan_code
                            or target_plan_revision != expected_plan_revision
                            or target_valid_until < expected_valid_until
                        ):
                            raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    elif action == "RENEW_VERIFIED":
                        if expected_status not in {"active", "trial"} or (
                            target_plan_code != expected_plan_code
                            or target_plan_revision != expected_plan_revision
                            or target_valid_until <= expected_valid_until
                        ):
                            raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    elif action == "APPLY_UPGRADE":
                        if expected_status != "active" or (
                            target_valid_until != expected_valid_until
                            or stamp >= expected_valid_until
                            or (target_plan_code, target_plan_revision) ==
                            (expected_plan_code, expected_plan_revision)
                        ):
                            raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    elif action == "APPLY_DOWNGRADE":
                        if expected_status != "active" or (
                            stamp < expected_valid_until
                            or target_valid_until <= expected_valid_until
                            or (target_plan_code, target_plan_revision) ==
                            (expected_plan_code, expected_plan_revision)
                        ):
                            raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    version = db.get(PlanVersionORM, (
                        target_plan_code, target_plan_revision,
                    ))
                    if version is None or version.status != "published":
                        raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    metrics = set(db.scalars(select(PlanLimitORM.resource).where(
                        PlanLimitORM.plan_code == target_plan_code,
                        PlanLimitORM.revision == target_plan_revision,
                    )).all())
                    if not {"ai.requests", "ai.total_tokens"}.issubset(metrics):
                        raise CommercialLicenseTransitionDenied("license.commercial_denied")
                    result_status = "active"
                    license_row.plan_code = target_plan_code
                    license_row.plan_revision = target_plan_revision
                    license_row.period_ends_at = datetime.fromtimestamp(
                        target_valid_until, tz=UTC,
                    )
                license_row.status = result_status
                license_row.updated_at = now
                db.add(CommercialLicenseTransitionAuditORM(
                    command_request_id=command_request_id,
                    key_id=kid, nonce=nonce, tenant_id=tenant_id,
                    actor_id=actor_user_id, action=action,
                    expected_status=expected_status,
                    result_status=result_status,
                    old_plan_code=expected_plan_code,
                    old_plan_revision=expected_plan_revision,
                    new_plan_code=target_plan_code,
                    new_plan_revision=target_plan_revision,
                    old_valid_until=expected_valid_until,
                    new_valid_until=target_valid_until,
                    verified_payment_ref=verified_payment_ref,
                    applied_at=now,
                ))
                db.flush()
                return result_status
        except IntegrityError as exc:
            raise CommercialLicenseTransitionDenied("license.commercial_denied") from exc
