"""Command-signed administrative authority for Core bridge identities.

Command proves human platform_admin + step-up before signing this request.
Assistant independently checks a dedicated service MAC, trusted FM organization,
step-up freshness and replay before a strictly scoped SQL transaction.
No API can issue, return or rotate the HMAC signing key.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .command_bridge_control_models import CommandBridgeControlEventORM
from .core_bridge_models import CoreBridgeGrantORM, CoreBridgeIdentityORM
from .db import TenantORM, UnitORM

PATH = "/internal/v1/command/core-bridge/manage"
STATUS_PATH = "/internal/v1/command/core-bridge/status"
_ACTIONS = frozenset({"provision", "grant", "revoke_grant", "revoke_identity"})
_SCOPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
WINDOW_SECONDS = 60
STEP_UP_SECONDS = 300


class CommandBridgeDenied(PermissionError):
    """Uniform denial, without caller, signer, tenant or secret details."""


def signed_control_message(
    *, key_id: str, timestamp: str, nonce: str, body: bytes, path: str = PATH
) -> bytes:
    return (
        f"POST\n{path}\n{key_id}\n{timestamp}\n{nonce}\n"
        f"{hashlib.sha256(body).hexdigest()}"
    ).encode("ascii")


def sign_command_control(
    *, key: str, key_id: str, timestamp: str, nonce: str, body: bytes,
    path: str = PATH,
) -> str:
    return hmac.new(
        key.encode("utf-8"),
        signed_control_message(
            key_id=key_id, timestamp=timestamp, nonce=nonce, body=body, path=path
        ),
        hashlib.sha256,
    ).hexdigest()


class CommandBridgeControlService:
    def __init__(
        self,
        *,
        sessions,
        command_key_id: str | None,
        command_signing_key: str | None,
        trusted_organization: str | None,
        core_key_id: str | None,
    ) -> None:
        self._sessions = sessions
        self._command_key_id = command_key_id
        self._command_key = command_signing_key
        self._organization = trusted_organization
        self._core_key_id = core_key_id

    def execute(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str | None],
        action: str,
        tenant_id: str,
        unit_id: str,
        capability: str,
        target_key_id: str,
        actor_user_id: str,
        organization_id: str,
        step_up_at: int,
        command_request_id: str,
    ) -> str:
        if not all((
            self._command_key_id,
            self._command_key,
            self._organization,
            self._core_key_id,
        )) or len(self._command_key or "") < 32:
            raise CommandBridgeDenied("command_bridge_denied")
        key_id = headers.get("key_id") or ""
        timestamp = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        signature = headers.get("signature") or ""
        if (
            not _KEY_ID.fullmatch(key_id)
            or key_id != self._command_key_id
            or not _NONCE.fullmatch(nonce)
            or not timestamp.isascii()
            or not timestamp.isdecimal()
            or len(timestamp) != 10
            or len(signature) != 64
            or len(raw_body) > 4096
        ):
            raise CommandBridgeDenied("command_bridge_denied")
        now = datetime.now(UTC)
        now_unix = int(now.timestamp())
        if abs(now_unix - int(timestamp)) > WINDOW_SECONDS:
            raise CommandBridgeDenied("command_bridge_denied")
        correct = sign_command_control(
            key=self._command_key or "",
            key_id=key_id,
            timestamp=timestamp,
            nonce=nonce,
            body=raw_body,
        )
        if not hmac.compare_digest(signature, correct):
            raise CommandBridgeDenied("command_bridge_denied")
        if (
            action not in _ACTIONS
            or organization_id != self._organization
            or target_key_id != self._core_key_id
            or not all(
                isinstance(value, str) and _SCOPE.fullmatch(value)
                for value in (
                    tenant_id, unit_id, capability, actor_user_id,
                    command_request_id,
                )
            )
            or type(step_up_at) is not int
            or step_up_at > now_unix + 15
            or now_unix - step_up_at > STEP_UP_SECONDS
        ):
            raise CommandBridgeDenied("command_bridge_denied")
        if action == "revoke_identity":
            # Global revocation is allowed only for the exact configured Core ID.
            # Tenant and unit are still signed as an accountable request scope.
            pass
        outcome = "denied"
        try:
            with self._sessions.begin() as db:
                tenant = db.get(TenantORM, tenant_id)
                unit = db.get(UnitORM, (tenant_id, unit_id))
                authorized_scope = bool(
                    tenant and tenant.status == "active"
                    and unit and unit.status == "active"
                )
                identity = db.scalar(
                    select(CoreBridgeIdentityORM)
                    .where(CoreBridgeIdentityORM.key_id == target_key_id)
                    .with_for_update()
                )
                if action == "provision" and authorized_scope and identity is None:
                    db.add(CoreBridgeIdentityORM(
                        key_id=target_key_id, active=True, revoked_at=None,
                        created_at=now,
                    ))
                    outcome = "provisioned"
                elif action == "grant" and authorized_scope and identity:
                    if identity.active and identity.revoked_at is None:
                        grant = db.scalar(
                            select(CoreBridgeGrantORM).where(
                                CoreBridgeGrantORM.key_id == target_key_id,
                                CoreBridgeGrantORM.tenant_id == tenant_id,
                                CoreBridgeGrantORM.unit_id == unit_id,
                                CoreBridgeGrantORM.capability == capability,
                            ).with_for_update()
                        )
                        if grant is None:
                            db.add(CoreBridgeGrantORM(
                                key_id=target_key_id,
                                tenant_id=tenant_id,
                                unit_id=unit_id,
                                capability=capability,
                                active=True,
                                revoked_at=None,
                                created_at=now,
                            ))
                            outcome = "granted"
                elif action == "revoke_grant" and identity:
                    grant = db.scalar(
                        select(CoreBridgeGrantORM).where(
                            CoreBridgeGrantORM.key_id == target_key_id,
                            CoreBridgeGrantORM.tenant_id == tenant_id,
                            CoreBridgeGrantORM.unit_id == unit_id,
                            CoreBridgeGrantORM.capability == capability,
                        ).with_for_update()
                    )
                    if grant and grant.active and grant.revoked_at is None:
                        grant.active = False
                        grant.revoked_at = now
                        outcome = "revoked"
                elif action == "revoke_identity" and identity:
                    if identity.active and identity.revoked_at is None:
                        identity.active = False
                        identity.revoked_at = now
                        grants = db.scalars(
                            select(CoreBridgeGrantORM)
                            .where(CoreBridgeGrantORM.key_id == target_key_id)
                            .with_for_update()
                        ).all()
                        for grant in grants:
                            grant.active = False
                            if grant.revoked_at is None:
                                grant.revoked_at = now
                        outcome = "revoked"
                db.add(CommandBridgeControlEventORM(
                    event_id=str(uuid4()),
                    nonce=nonce,
                    key_id=target_key_id,
                    tenant_id=tenant_id,
                    unit_id=unit_id,
                    capability=capability,
                    action=action,
                    actor_user_id=actor_user_id,
                    command_request_id=command_request_id,
                    outcome=outcome,
                    created_at=now,
                ))
                db.flush()
        except IntegrityError as exc:
            raise CommandBridgeDenied("command_bridge_denied") from exc
        if outcome == "denied":
            raise CommandBridgeDenied("command_bridge_denied")
        return outcome


    def reconcile_status(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str | None],
        action: str,
        tenant_id: str,
        unit_id: str,
        capability: str,
        target_key_id: str,
        actor_user_id: str,
        organization_id: str,
        step_up_at: int,
        command_request_id: str,
    ) -> dict[str, str | None]:
        """Inspect an existing mutation outcome without mutating grants or identities.

        Unknown is never evidence that a timed-out mutation did NOT commit.
        Status signatures have a different path from mutation signatures.
        """
        if not all((
            self._command_key_id,
            self._command_key,
            self._organization,
            self._core_key_id,
        )) or len(self._command_key or "") < 32:
            raise CommandBridgeDenied("command_bridge_denied")
        key_id = headers.get("key_id") or ""
        timestamp = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        signature = headers.get("signature") or ""
        if (
            not _KEY_ID.fullmatch(key_id)
            or key_id != self._command_key_id
            or not _NONCE.fullmatch(nonce)
            or not timestamp.isascii()
            or not timestamp.isdecimal()
            or len(timestamp) != 10
            or len(signature) != 64
            or len(raw_body) > 4096
        ):
            raise CommandBridgeDenied("command_bridge_denied")
        now_unix = int(datetime.now(UTC).timestamp())
        if abs(now_unix - int(timestamp)) > WINDOW_SECONDS:
            raise CommandBridgeDenied("command_bridge_denied")
        expected = sign_command_control(
            key=self._command_key or "",
            key_id=key_id,
            timestamp=timestamp,
            nonce=nonce,
            body=raw_body,
            path=STATUS_PATH,
        )
        if not hmac.compare_digest(signature, expected):
            raise CommandBridgeDenied("command_bridge_denied")
        if (
            action not in _ACTIONS
            or organization_id != self._organization
            or target_key_id != self._core_key_id
            or not all(
                isinstance(value, str) and _SCOPE.fullmatch(value)
                for value in (
                    tenant_id, unit_id, capability, actor_user_id,
                    command_request_id,
                )
            )
            or type(step_up_at) is not int
            or step_up_at > now_unix + 15
            or now_unix - step_up_at > STEP_UP_SECONDS
        ):
            raise CommandBridgeDenied("command_bridge_denied")
        with self._sessions() as db:
            event = db.scalar(
                select(CommandBridgeControlEventORM).where(
                    CommandBridgeControlEventORM.command_request_id
                    == command_request_id
                )
            )
            if event is None:
                return {"status": "unknown", "outcome": None}
            if (
                event.key_id != target_key_id
                or event.tenant_id != tenant_id
                or event.unit_id != unit_id
                or event.capability != capability
                or event.action != action
                or event.actor_user_id != actor_user_id
            ):
                # Hide the presence of an event in another scope or actor.
                return {"status": "unknown", "outcome": None}
            if event.outcome in {"provisioned", "granted", "revoked"}:
                return {"status": "applied", "outcome": event.outcome}
            return {"status": "denied", "outcome": "denied"}
