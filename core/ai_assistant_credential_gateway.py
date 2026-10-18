"""Authenticated Core -> Assistant BYOK credential bridge.

TLS, HMAC-SHA256 per request, 60s timestamp, random nonce, exact tenant+unit
+capability, and no bearer secrets in logs. No implicit key provisioning.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlsplit

import httpx

from core.ai_tenant_credential_resolver import TenantCredentialDenied
from core.seguranca.segredos import SecretValue

PATH = "/internal/v1/core/credentials/resolve"


class AssistantSignedCredentialGateway:
    """TenantCredentialGateway implementation using a scoped service identity."""

    def __init__(
        self,
        *,
        base_url: str,
        key_id: str,
        signing_key: str,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
        allow_test_http: bool = False,
    ) -> None:
        parsed = urlsplit(base_url)
        allowed_http = allow_test_http and parsed.hostname == "testserver"
        if (
            parsed.scheme != "https" and not (allowed_http and parsed.scheme == "http")
        ) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("assistant_bridge_https_origin_required")
        if not key_id or len(key_id) > 64 or not key_id.replace("-", "").replace("_", "").replace(".", "").isalnum():
            raise ValueError("assistant_bridge_key_id_invalid")
        if not signing_key or len(signing_key) < 32:
            raise ValueError("assistant_bridge_signing_key_invalid")
        if not 0 < timeout_seconds <= 10:
            raise ValueError("assistant_bridge_timeout_invalid")
        self._url = base_url.rstrip("/") + PATH
        self._key_id = key_id
        self._key = signing_key
        self._timeout = timeout_seconds
        self._client = client

    def resolve_active_secret(self, *, tenant_id: str, opaque_reference: str) -> SecretValue:
        # Core must propagate unit/capability; old unscoped port is never usable.
        raise TenantCredentialDenied("core_control_plane.byok_scope_required")

    def resolve_scoped_secret(
        self, *, tenant_id: str, unit_id: str, capability: str, opaque_reference: str
    ) -> SecretValue:
        if not all(
            isinstance(value, str) and 0 < len(value) <= 160
            for value in (tenant_id, unit_id, capability, opaque_reference)
        ):
            raise TenantCredentialDenied("core_control_plane.byok_scope_invalid")
        if len(opaque_reference) > 64:
            raise TenantCredentialDenied("core_control_plane.byok_scope_invalid")
        body = json.dumps(
            {
                "tenant_id": tenant_id,
                "unit_id": unit_id,
                "capability": capability,
                "connection_id": opaque_reference,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(24)
        message = (
            f"POST\n{PATH}\n{self._key_id}\n{timestamp}\n{nonce}\n"
            f"{hashlib.sha256(body).hexdigest()}"
        ).encode("ascii")
        signature = hmac.new(
            self._key.encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-FM-Core-Key-ID": self._key_id,
            "X-FM-Core-Timestamp": timestamp,
            "X-FM-Core-Nonce": nonce,
            "X-FM-Core-Signature": signature,
        }
        try:
            if self._client is not None:
                response = self._client.post(
                    self._url, content=body, headers=headers, timeout=self._timeout
                )
            else:
                with httpx.Client(
                    timeout=self._timeout, trust_env=False, follow_redirects=False
                ) as client:
                    response = client.post(self._url, content=body, headers=headers)
            if response.status_code != 200 or len(response.content) > 4096:
                raise TenantCredentialDenied("core_control_plane.byok_denied")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid_response")
            secret = payload.get("secret")
            if not isinstance(secret, str) or not secret or len(secret) > 8192:
                raise ValueError("invalid_secret")
            return SecretValue(secret)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise TenantCredentialDenied("core_control_plane.byok_denied") from exc
