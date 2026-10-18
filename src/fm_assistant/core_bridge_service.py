"""Authenticated Core->Assistant BYOK bridge (disabled without explicit key).

No public user/session auth accepted; requests must be service HMAC signed,
time-bound and replay-protected. DB identity/grants are OFF by default.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .core_bridge_models import (
    CoreBridgeAccessORM,
    CoreBridgeGrantORM,
    CoreBridgeIdentityORM,
)
from .core_byok_release_policy import CoreBYOKReleasePolicy
from .db import IntegrationConnectionORM, IntegrationSecretVersionORM
from .credential_vault import CredentialVault

PATH = "/internal/v1/core/credentials/resolve"
KEY_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
NONCE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{22,96}$")
WINDOW_SECONDS = 60


class CoreBridgeDenied(PermissionError):
    """No tenant, key or secret detail in error string."""


def canonical_signature_message(
    *, key_id: str, timestamp: str, nonce: str, body: bytes
) -> bytes:
    return (
        f"POST\n{PATH}\n{key_id}\n{timestamp}\n{nonce}\n"
        f"{hashlib.sha256(body).hexdigest()}"
    ).encode("ascii")


def sign_core_bridge(
    *, key: str, key_id: str, timestamp: str, nonce: str, body: bytes
) -> str:
    return hmac.new(
        key.encode("utf-8"),
        canonical_signature_message(
            key_id=key_id, timestamp=timestamp, nonce=nonce, body=body
        ),
        hashlib.sha256,
    ).hexdigest()


class CoreBridgeService:
    def __init__(
        self,
        *,
        sessions,
        vault: CredentialVault,
        key_id: str | None,
        signing_key: str | None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._vault = vault
        self._key_id = key_id
        self._key = signing_key
        self._now = now
        self._policy = CoreBYOKReleasePolicy(sessions)

    def resolve(
        self,
        *,
        headers: dict[str, str | None],
        raw_body: bytes,
        tenant_id: str,
        unit_id: str,
        capability: str,
        connection_id: str,
    ) -> str:
        if not self._key_id or not self._key or len(self._key) < 32:
            raise CoreBridgeDenied("core_bridge_denied")
        key_id = headers.get("key_id") or ""
        timestamp = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        signature = headers.get("signature") or ""
        if (
            not KEY_ID_PATTERN.fullmatch(key_id)
            or key_id != self._key_id
            or not NONCE_PATTERN.fullmatch(nonce)
            or not timestamp.isascii()
            or not timestamp.isdecimal()
            or len(timestamp) != 10
            or len(signature) != 64
            or len(raw_body) > 4096
        ):
            raise CoreBridgeDenied("core_bridge_denied")
        current = self._now().astimezone(UTC)
        if abs(int(current.timestamp()) - int(timestamp)) > WINDOW_SECONDS:
            raise CoreBridgeDenied("core_bridge_denied")
        expected = sign_core_bridge(
            key=self._key,
            key_id=key_id,
            timestamp=timestamp,
            nonce=nonce,
            body=raw_body,
        )
        if not hmac.compare_digest(signature, expected):
            raise CoreBridgeDenied("core_bridge_denied")
        denied = False
        resolved: str | None = None
        try:
            with self._sessions.begin() as db:
                # Lock identity/grant/connection on PostgreSQL until audit commits.
                identity = db.scalar(
                    select(CoreBridgeIdentityORM)
                    .where(CoreBridgeIdentityORM.key_id == key_id)
                    .with_for_update()
                )
                grant = db.scalar(
                    select(CoreBridgeGrantORM)
                    .where(
                        CoreBridgeGrantORM.key_id == key_id,
                        CoreBridgeGrantORM.tenant_id == tenant_id,
                        CoreBridgeGrantORM.unit_id == unit_id,
                        CoreBridgeGrantORM.capability == capability,
                    )
                    .with_for_update()
                )
                allowed = bool(
                    identity and identity.active and identity.revoked_at is None
                    and grant and grant.active and grant.revoked_at is None
                )
                if allowed:
                    connection = db.scalar(
                        select(IntegrationConnectionORM)
                        .where(
                            IntegrationConnectionORM.connection_id == connection_id,
                            IntegrationConnectionORM.tenant_id == tenant_id,
                            IntegrationConnectionORM.unit_id == unit_id,
                            IntegrationConnectionORM.status == "active",
                        )
                        .with_for_update()
                    )
                    allowed = bool(
                        connection
                        and self._policy.eligible(
                            tenant_id=tenant_id,
                            unit_id=unit_id,
                            connection_id=connection_id,
                            capability=capability,
                            now=current,
                            db=db,
                        )
                    )
                secret = None
                if allowed:
                    secret = db.scalar(
                        select(IntegrationSecretVersionORM)
                        .where(
                            IntegrationSecretVersionORM.connection_id == connection_id,
                            IntegrationSecretVersionORM.secret_name == "api_key",
                            IntegrationSecretVersionORM.source == "tenant_managed",
                            IntegrationSecretVersionORM.active.is_(True),
                            IntegrationSecretVersionORM.revoked_at.is_(None),
                        )
                        .order_by(IntegrationSecretVersionORM.version.desc())
                        .limit(1)
                        .with_for_update()
                    )
                if (
                    allowed and secret and secret.storage_backend == "db_encrypted"
                    and secret.ciphertext
                ):
                    # Decrypt inside same transaction as authorization and audit.
                    resolved = self._vault.decrypt(secret.ciphertext)
                denied = not bool(resolved)
                db.add(
                    CoreBridgeAccessORM(
                        key_id=key_id,
                        nonce=nonce,
                        tenant_id=tenant_id[:128],
                        unit_id=unit_id[:128],
                        capability=capability[:160],
                        connection_id=connection_id[:64],
                        outcome="denied" if denied else "released",
                        created_at=current,
                    )
                )
                db.flush()
        except IntegrityError as exc:
            # Unique (key_id, nonce) fails closed, even when replayed across tenants.
            raise CoreBridgeDenied("core_bridge_denied") from exc
        if denied or resolved is None:
            raise CoreBridgeDenied("core_bridge_denied")
        return resolved
