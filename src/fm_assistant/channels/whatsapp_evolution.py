"""FM-managed QR connection transport. No tenant or browser receives master keys.

Provider protocol is pinned behind this adapter and must be certified against
the chosen Evolution release before production use.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx


class EvolutionUnavailable(RuntimeError):
    """Sanitized gateway failure: execution outcome may be ambiguous."""


@dataclass(frozen=True, kw_only=True)
class EvolutionSettings:
    origin: str
    global_key: str = field(repr=False)
    timeout_seconds: float = 8.0

    def __post_init__(self) -> None:
        url = urlsplit(self.origin)
        if (
            url.scheme != "https" or not url.hostname
            or url.path not in {"", "/"} or url.query or url.fragment
            or url.username or url.password or url.port not in (None, 443)
            or url.hostname in {"localhost", "127.0.0.1", "::1"}
            or url.hostname.endswith(".local")
            or not isinstance(self.global_key, str) or len(self.global_key) < 32
            or not 1 <= self.timeout_seconds <= 30
        ):
            raise ValueError("evolution_settings_invalid")


class EvolutionClient:
    def __init__(self, settings: EvolutionSettings, *, client: httpx.Client | None = None):
        self._settings = settings
        self._client = client

    def _request(
        self, method: str, path: str, *, payload: dict | None = None,
        instance_token: str | None = None,
    ) -> dict:
        if instance_token is not None and (
            not isinstance(instance_token, str) or not 16 <= len(instance_token) <= 4096
        ):
            raise EvolutionUnavailable("evolution_instance_token_invalid")
        headers = {"apikey": instance_token or self._settings.global_key}
        try:
            if self._client is None:
                with httpx.Client(trust_env=False, follow_redirects=False) as client:
                    response = client.request(
                        method, self._settings.origin.rstrip("/") + path,
                        json=payload, headers=headers,
                        timeout=self._settings.timeout_seconds,
                    )
            else:
                response = self._client.request(
                    method, self._settings.origin.rstrip("/") + path,
                    json=payload, headers=headers,
                    timeout=self._settings.timeout_seconds,
                    follow_redirects=False,
                )
            if response.status_code not in {200, 201} or len(response.content) > 262144:
                raise EvolutionUnavailable("evolution_gateway_unavailable")
            data = response.json()
            if not isinstance(data, dict):
                raise EvolutionUnavailable("evolution_payload_invalid")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            raise EvolutionUnavailable("evolution_gateway_unavailable") from exc

    @staticmethod
    def _instance(value: str) -> str:
        if not isinstance(value, str) or re.fullmatch(r"[a-z0-9_-]{8,96}", value) is None:
            raise ValueError("evolution_instance_invalid")
        return value

    def create(self, instance: str) -> str:
        name = self._instance(instance)
        data = self._request("POST", "/instance/create", payload={
            "instanceName": name, "qrcode": True, "integration": "WHATSAPP-BAILEYS",
        })
        token = data.get("hash")
        token = token.get("token") if isinstance(token, dict) else None
        if not isinstance(token, str) or not token.strip() or len(token) > 4096:
            raise EvolutionUnavailable("evolution_token_missing")
        return token

    API_FAMILY = "evolution_v2_whatsapp_baileys"
    CONTRACT_BASELINE = "v2.3.7"
    WEBHOOK_EVENTS = ("MESSAGES_UPSERT", "MESSAGES_UPDATE", "CONNECTION_UPDATE")

    def set_native_webhook(
        self, instance: str, *, instance_token: str,
        url: str, auth_token: str,
    ) -> None:
        """Configure the per-instance v2 webhook, never a global unauthenticated hook."""
        endpoint = urlsplit(url)
        if (
            endpoint.scheme != "https" or not endpoint.hostname
            or endpoint.username or endpoint.password or endpoint.fragment
            or endpoint.query or endpoint.port not in (None, 443)
            or endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            or (endpoint.hostname or "").endswith(".local")
            or not endpoint.path.startswith("/webhooks/evolution-native/")
            or not isinstance(auth_token, str) or len(auth_token) < 32
        ):
            raise ValueError("evolution_native_hook_invalid")
        data = self._request(
            "POST", "/webhook/set/" + self._instance(instance),
            instance_token=instance_token,
            payload={"webhook": {
                "enabled": True, "url": url, "byEvents": False,
                "base64": False,
                "headers": {"X-FM-Evolution-Token": auth_token},
                "events": list(self.WEBHOOK_EVENTS),
            }},
        )
        webhook = data.get("webhook")
        if isinstance(webhook, dict) and "webhook" in webhook:
            webhook = webhook["webhook"]
        if not isinstance(webhook, dict) or webhook.get("enabled") is not True:
            raise EvolutionUnavailable("evolution_native_hook_unconfirmed")
        if webhook.get("url") != url:
            raise EvolutionUnavailable("evolution_native_hook_unconfirmed")

    def send_text(
        self, instance: str, *, instance_token: str, recipient: str,
        message: str,
    ) -> str:
        """One outbound attempt only; ambiguous outcomes are never retried."""
        name = self._instance(instance)
        if (
            not isinstance(recipient, str)
            or re.fullmatch(r"[0-9]{8,20}", recipient) is None
            or not isinstance(message, str) or not 1 <= len(message.strip()) <= 20000
        ):
            raise ValueError("evolution_outbound_invalid")
        data = self._request(
            "POST", "/message/sendText/" + name,
            payload={"number": recipient, "text": message.strip()},
            instance_token=instance_token,
        )
        key = data.get("key")
        reference = key.get("id") if isinstance(key, dict) else data.get("id")
        if not isinstance(reference, str) or not 1 <= len(reference) <= 128:
            raise EvolutionUnavailable("evolution_delivery_uncertain")
        return reference

    def find_outbound_evidence(
        self, instance: str, *, instance_token: str, provider_reference: str,
    ) -> str | None:
        """Read-only provider lookup; returns evidence digest, not delivery proof.

        Exact Evolution v2.3.7 response compatibility still needs external
        homologation. Never infer ownership from recipient/text/timestamps.
        """
        if (
            not isinstance(provider_reference, str)
            or re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", provider_reference) is None
        ):
            raise ValueError("evolution_provider_reference_invalid")
        data = self._request(
            "POST", "/chat/findMessages/" + self._instance(instance),
            payload={"where": {"key": {"id": provider_reference}}},
            instance_token=instance_token,
        )
        page = data.get("messages")
        records = page.get("records") if isinstance(page, dict) else None
        if not isinstance(records, list) or len(records) > 100:
            raise EvolutionUnavailable("evolution_evidence_unverifiable")
        matches = [
            item for item in records
            if isinstance(item, dict)
            and isinstance(item.get("key"), dict)
            and item["key"].get("id") == provider_reference
            and item["key"].get("fromMe") is True
        ]
        if len(matches) != 1:
            return None
        import hashlib
        import json

        # Hash the actual provider response, never persist the record body.
        return hashlib.sha256(
            json.dumps(matches[0], sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def connection_state(self, instance: str, *, instance_token: str) -> str:
        """Read current remote state on the Evolution v2-compatible adapter."""
        data = self._request(
            "GET", "/instance/connectionState/" + self._instance(instance),
            instance_token=instance_token,
        )
        obj = data.get("instance")
        state = obj.get("state") if isinstance(obj, dict) else None
        if state not in {"open", "close", "connecting"}:
            raise EvolutionUnavailable("evolution_state_unverified")
        return state

    def logout(self, instance: str, *, instance_token: str) -> None:
        """Single remote logout attempt; never assume success from HTTP alone."""
        data = self._request(
            "DELETE", "/instance/logout/" + self._instance(instance),
            instance_token=instance_token,
        )
        if data.get("status") not in {"success", "SUCCESS"} and (
            data.get("message") not in {"success", "SUCCESS"}
        ):
            raise EvolutionUnavailable("evolution_logout_unconfirmed")

    def connect(self, instance: str) -> str | None:
        data = self._request("GET", "/instance/connect/" + self._instance(instance))
        instance_state = data.get("instance")
        if data.get("status") in {"connected", "open"} or (
            isinstance(instance_state, dict) and instance_state.get("state") == "open"
        ):
            return None
        qr = data.get("base64")
        if qr is None and isinstance(data.get("qrcode"), dict):
            qr = data["qrcode"].get("base64")
        if not isinstance(qr, str) or len(qr) > 262144:
            raise EvolutionUnavailable("evolution_qr_unavailable")
        encoded = qr.split(",", 1)[-1]
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise EvolutionUnavailable("evolution_qr_invalid") from exc
        if not 100 <= len(decoded) <= 196608 or not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise EvolutionUnavailable("evolution_qr_invalid")
        return "data:image/png;base64," + encoded
