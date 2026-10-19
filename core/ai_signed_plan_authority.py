"""Read-through verification of Assistant-issued plan grants.

Every resolve fetches a fresh, short-lived signed assertion. No cache is allowed:
revocation, unavailable transport and malformed grants fail closed. The trusted
transport itself must authenticate the Assistant service and enforce TLS.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import UTC, datetime
from typing import Callable
from urllib.parse import urlsplit

import httpx

from core.ai_plan_usage_guard import PlanQuotaPolicy
from core.ai_quota_store import QuotaDenied

PATH = "/internal/v1/assistant/core-plan-grant"
METRICS = frozenset({
    "ai.requests", "ai.total_tokens", "ai.input_tokens",
    "ai.output_tokens", "ai.cached_tokens",
})


def signed_plan_body(*, secret: bytes, body: bytes) -> str:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise QuotaDenied("core_plan.signer_unavailable")
    return hmac.new(secret, PATH.encode() + b"\n" + body, hashlib.sha256).hexdigest()


class SignedAssistantPlanAuthority:
    """PolicyAuthority backed by a fresh authenticated Assistant assertion.

    fetch(tenant_id, unit_id, capability) returns a pair of raw JSON bytes and
    lowercase hex MAC, or raises on outage. The caller must never construct this
    from browser input or route directly to an untrusted hostname.
    """

    def __init__(
        self, *, secret: bytes,
        fetch: Callable[[str, str, str, str], tuple[bytes, str]],
    ) -> None:
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("core_plan.signer_unavailable")
        self._secret = secret
        self._fetch = fetch

    def resolve(
        self, *, tenant_id: str, unit_id: str, capability: str,
        now: datetime,
    ) -> PlanQuotaPolicy:
        if (
            not all(isinstance(v, str) and bool(v) and len(v) <= 128
                    for v in (tenant_id, unit_id, capability))
            or now.tzinfo is None or now.utcoffset() is None
        ):
            raise QuotaDenied("core_plan.scope_invalid")
        challenge = secrets.token_urlsafe(24)
        try:
            raw, signature = self._fetch(tenant_id, unit_id, capability, challenge)
            if (
                not isinstance(raw, bytes) or len(raw) > 8192
                or not isinstance(signature, str) or len(signature) != 64
                or not hmac.compare_digest(
                    signed_plan_body(secret=self._secret, body=raw), signature
                )
            ):
                raise QuotaDenied("core_plan.signature_invalid")
            obj = json.loads(raw)
            if not isinstance(obj, dict) or set(obj) != {
                "tenant_id", "unit_id", "capability", "challenge", "plan_code", "revision",
                "expires_at", "licensed_until", "input_bound",
                "output_bound", "scopes",
            }:
                raise QuotaDenied("core_plan.grant_invalid")
            if (
                obj["tenant_id"] != tenant_id or obj["unit_id"] != unit_id
                or obj["capability"] != capability
                or obj["challenge"] != challenge
                or not isinstance(obj["expires_at"], int)
                or type(obj["expires_at"]) is not int
                or type(obj["licensed_until"]) is not int
                or not isinstance(obj["scopes"], list)
                or not 2 <= len(obj["scopes"]) <= 5
                or any(
                    not isinstance(v, list) or len(v) != 2
                    or not all(isinstance(z, str) for z in v)
                    for v in obj["scopes"]
                )
            ):
                raise QuotaDenied("core_plan.grant_invalid")
            current = int(now.astimezone(UTC).timestamp())
            # Short signed grants cannot outlive the canonical license.
            if not current < obj["expires_at"] <= current + 60:
                raise QuotaDenied("core_plan.grant_expired")
            if obj["licensed_until"] <= current:
                raise QuotaDenied("core_plan.license_expired")
            return PlanQuotaPolicy(
                tenant_id=tenant_id, unit_id=unit_id,
                plan_code=obj["plan_code"], revision=obj["revision"],
                valid_until=datetime.fromtimestamp(
                    min(obj["expires_at"], obj["licensed_until"]), tz=UTC
                ),
                input_bound=obj["input_bound"],
                output_bound=obj["output_bound"],
                scopes=tuple((v[0], v[1]) for v in obj["scopes"]),
            )
        except QuotaDenied:
            raise
        except (Exception,) as exc:
            raise QuotaDenied("core_plan.grant_unavailable") from exc


class AssistantPlanHTTPSFetch:
    """Explicit HTTPS-only adapter for the Core's trusted policy read port.

    Token ceilings come from a server-controlled capability configuration,
    never from the browser or an arbitrary tenant request.
    """

    def __init__(
        self, *, origin: str, secret: bytes,
        bounds: Callable[[str], tuple[int, int]],
        client: httpx.Client,
    ) -> None:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment
            or parsed.port not in (None, 443)
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            or parsed.hostname.endswith(".local")
            or not isinstance(secret, bytes) or len(secret) < 32
        ):
            raise ValueError("core_plan.endpoint_invalid")
        self._origin = origin.rstrip("/")
        self._secret = secret
        self._bounds = bounds
        self._client = client

    def __call__(
        self, tenant_id: str, unit_id: str, capability: str,
        challenge: str,
    ) -> tuple[bytes, str]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{22,96}", challenge):
            raise QuotaDenied("core_plan.challenge_invalid")
        try:
            input_bound, output_bound = self._bounds(capability)
            if (
                type(input_bound) is not int or type(output_bound) is not int
                or input_bound <= 0 or output_bound <= 0
                or input_bound + output_bound > 2_000_000_000
            ):
                raise QuotaDenied("core_plan.bounds_invalid")
            raw = json.dumps({
                "tenant_id": tenant_id,
                "unit_id": unit_id,
                "capability": capability,
                "challenge": challenge,
                "input_bound": input_bound,
                "output_bound": output_bound,
                "requested_at": int(datetime.now(UTC).timestamp()),
            }, sort_keys=True, separators=(",", ":")).encode()
            signature = hmac.new(
                self._secret, b"POST\n" + PATH.encode() + b"\n" + raw,
                hashlib.sha256,
            ).hexdigest()
            response = self._client.post(
                self._origin + PATH, content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-FM-Core-Plan-Signature": signature,
                },
                follow_redirects=False, timeout=5,
            )
            if response.status_code != 200 or len(response.content) > 8192:
                raise QuotaDenied("core_plan.grant_unavailable")
            return (
                response.content,
                response.headers.get("X-FM-Assistant-Plan-Signature", ""),
            )
        except QuotaDenied:
            raise
        except (ValueError, httpx.HTTPError) as exc:
            raise QuotaDenied("core_plan.grant_unavailable") from exc
