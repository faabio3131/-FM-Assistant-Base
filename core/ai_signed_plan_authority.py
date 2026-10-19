"""Read-through verification of Assistant-issued plan grants.

Every resolve fetches a fresh, short-lived signed assertion. No cache is allowed:
revocation, unavailable transport and malformed grants fail closed. The trusted
transport itself must authenticate the Assistant service and enforce TLS.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from typing import Callable

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
