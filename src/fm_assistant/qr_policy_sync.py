"""Signed, revision-monotonic FM Command WhatsApp QR display policy projection.

Corporate Command remains the sole authority. This controls display only,
not the Evolution/WhatsApp provider's QR lifetime. No tenant endpoint can
mutate it, and the policy applies to all Assistant tenants.
"""
from __future__ import annotations

import hmac
import json
import re
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from .command_bridge_control_service import sign_command_control
from .db import PlanSyncNonceORM, WhatsAppQRDisplayPolicyORM

PATH = "/internal/v1/command/whatsapp-qr/policy"
PRODUCT = "VENDEATENDEIA"
DEFAULT_SECONDS = 45
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")


class QrDisplayPolicyDenied(PermissionError):
    pass


class CommandQrDisplayPolicyService:
    def __init__(
        self, *, sessions, key_id: str | None, signing_key: str | None,
        trusted_organization: str | None,
    ) -> None:
        self._sessions = sessions
        self._key_id = key_id
        self._key = signing_key
        self._organization = trusted_organization

    def read(self) -> tuple[int, int]:
        with self._sessions() as db:
            current = db.get(WhatsAppQRDisplayPolicyORM, PRODUCT)
            return (
                (current.display_seconds, current.revision)
                if current is not None else (DEFAULT_SECONDS, 0)
            )

    def apply(
        self, *, raw_body: bytes, headers: dict[str, str | None],
        product_code: str, organization_id: str, actor_user_id: str,
        approved_at: int, revision: int, display_seconds: int,
    ) -> str:
        now = datetime.now(UTC)
        key_id = headers.get("key_id") or ""
        timestamp = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        signature = headers.get("signature") or ""
        if (
            not self._key or len(self._key) < 32 or not self._key_id
            or not self._organization or key_id != self._key_id
            or product_code != PRODUCT or organization_id != self._organization
            or not isinstance(actor_user_id, str)
            or not IDENTIFIER.fullmatch(actor_user_id)
            or not NONCE.fullmatch(nonce)
            or not timestamp.isascii() or not timestamp.isdecimal()
            or len(timestamp) != 10
            or abs(int(timestamp) - int(now.timestamp())) > 60
            or not re.fullmatch(r"[0-9a-f]{64}", signature)
            or not isinstance(raw_body, bytes) or len(raw_body) > 2048
            or type(approved_at) is not int
            or approved_at > int(now.timestamp()) + 15
            or approved_at < int(now.timestamp()) - 366 * 86400
            or type(revision) is not int or revision < 1
            or type(display_seconds) is not int
            or not 15 <= display_seconds <= 120
        ):
            raise QrDisplayPolicyDenied("qr_policy_denied")
        expected = sign_command_control(
            key=self._key, key_id=key_id,
            timestamp=timestamp, nonce=nonce,
            body=raw_body, path=PATH,
        )
        if not hmac.compare_digest(expected, signature):
            raise QrDisplayPolicyDenied("qr_policy_denied")
        try:
            actual = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise QrDisplayPolicyDenied("qr_policy_denied") from exc
        if actual != {
            "product_code": product_code,
            "organization_id": organization_id,
            "actor_user_id": actor_user_id,
            "approved_at": approved_at,
            "revision": revision,
            "display_seconds": display_seconds,
        }:
            raise QrDisplayPolicyDenied("qr_policy_denied")
        try:
            with self._sessions.begin() as db:
                db.add(PlanSyncNonceORM(
                    key_id=key_id, nonce=nonce, created_at=now,
                ))
                db.flush()  # Replay rejected before policy changes.
                current = db.get(
                    WhatsAppQRDisplayPolicyORM, PRODUCT, with_for_update=True,
                )
                if current is not None:
                    if revision < current.revision:
                        raise QrDisplayPolicyDenied("qr_policy_revision_old")
                    if revision == current.revision:
                        if (
                            current.display_seconds != display_seconds
                            or current.organization_id != organization_id
                            or current.actor_id != actor_user_id
                            or int(current.approved_at.replace(
                                tzinfo=UTC if current.approved_at.tzinfo is None
                                else current.approved_at.tzinfo
                            ).timestamp()) != approved_at
                        ):
                            raise QrDisplayPolicyDenied("qr_policy_revision_conflict")
                        return "already_projected"
                    current.display_seconds = display_seconds
                    current.revision = revision
                    current.actor_id = actor_user_id
                    current.approved_at = datetime.fromtimestamp(approved_at, UTC)
                    current.updated_at = now
                    return "projected"
                db.add(WhatsAppQRDisplayPolicyORM(
                    product_code=PRODUCT, organization_id=organization_id,
                    display_seconds=display_seconds, revision=revision,
                    actor_id=actor_user_id,
                    approved_at=datetime.fromtimestamp(approved_at, UTC),
                    updated_at=now,
                ))
                db.flush()
                return "projected"
        except IntegrityError as exc:
            # Concurrent initial imports, duplicate nonces and uniqueness
            # conflicts fail closed. Never silently accept stale policy.
            raise QrDisplayPolicyDenied("qr_policy_denied") from exc
