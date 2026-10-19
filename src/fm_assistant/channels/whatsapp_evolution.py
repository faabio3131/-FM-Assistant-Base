"""FM-managed QR connection transport. No tenant or browser receives master keys.

Provider protocol is pinned behind this adapter and must be certified against
the chosen Evolution release before production use.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


class EvolutionUnavailable(RuntimeError):
    """Sanitized gateway failure: execution outcome may be ambiguous."""


@dataclass(frozen=True, kw_only=True)
class EvolutionSettings:
    origin: str
    global_key: str
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

    def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        try:
            if self._client is None:
                with httpx.Client(trust_env=False, follow_redirects=False) as client:
                    response = client.request(
                        method, self._settings.origin.rstrip("/") + path,
                        json=payload, headers={"apikey": self._settings.global_key},
                        timeout=self._settings.timeout_seconds,
                    )
            else:
                response = self._client.request(
                    method, self._settings.origin.rstrip("/") + path,
                    json=payload, headers={"apikey": self._settings.global_key},
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

    def connect(self, instance: str) -> str | None:
        data = self._request("GET", "/instance/connect/" + self._instance(instance))
        if data.get("status") in {"connected", "open"} or data.get("instance", {}).get("state") == "open":
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
