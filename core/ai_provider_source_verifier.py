"""Cryptographic source verification before issuing FM evidence attestations.

Adapter contract for sources that actually sign their statements. Pin the
source key independently of webhook payloads. A normal unsigned LLM API
response MUST NOT be described as a provider signature or accepted here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.ai_quota_store import QuotaDenied
from core.ai_verified_usage_receipt import VerifiedProviderUsageReceipt


@dataclass(frozen=True, kw_only=True)
class ProviderSigningPolicy:
    issuer: str
    public_key: bytes
    max_age_seconds: int = 300

    def __post_init__(self) -> None:
        if (
            not isinstance(self.issuer, str) or not 1 <= len(self.issuer) <= 128
            or not isinstance(self.public_key, bytes)
            or len(self.public_key) != 32
            or type(self.max_age_seconds) is not int
            or not 30 <= self.max_age_seconds <= 3600
        ):
            raise ValueError("provider_source_policy_invalid")


def verified_signed_usage_source(
    *, payload: bytes, signature: bytes, policy: ProviderSigningPolicy,
    expected_request_id: str, expected_tenant_id: str,
    expected_unit_id: str, at: datetime | None = None,
) -> VerifiedProviderUsageReceipt:
    """Verify exact authenticated source bytes; reject unsigned/cross-scope/stale.

    Caller may store the returned typed receipt through the already trusted
    FM gateway's HMAC and immutable evidence ledger. No retry/settlement here.
    """
    if (
        not isinstance(payload, bytes) or not 1 <= len(payload) <= 8192
        or not isinstance(signature, bytes) or len(signature) != 64
    ):
        raise QuotaDenied("provider_source_unauthenticated")
    try:
        Ed25519PublicKey.from_public_bytes(policy.public_key).verify(
            signature, b"FM_PROVIDER_USAGE_SOURCE_V1\n" + payload,
        )
    except (InvalidSignature, ValueError) as exc:
        raise QuotaDenied("provider_source_unauthenticated") from exc
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or set(data) != {
            "issuer", "request_id", "tenant_id", "unit_id",
            "provider", "model", "input_tokens", "output_tokens",
            "cost_usd", "no_charge", "observed_at",
        }:
            raise ValueError("shape")
        if data["issuer"] != policy.issuer or (
            data["request_id"], data["tenant_id"], data["unit_id"],
        ) != (expected_request_id, expected_tenant_id, expected_unit_id):
            raise ValueError("scope")
        observed = data["observed_at"]
        if type(observed) is not int:
            raise ValueError("timestamp")
        now = int((at or datetime.now(UTC)).timestamp())
        if observed > now + 15 or now - observed > policy.max_age_seconds:
            raise ValueError("freshness")
        if type(data["no_charge"]) is not bool:
            raise ValueError("charge")
        cost = data["cost_usd"]
        if cost is not None and not isinstance(cost, str):
            raise ValueError("cost")
        return VerifiedProviderUsageReceipt(
            provider=data["provider"], model=data["model"],
            request_id=data["request_id"],
            tenant_id=data["tenant_id"], unit_id=data["unit_id"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            provider_cost_usd=Decimal(cost) if cost is not None else None,
            no_charge=data["no_charge"],
            evidence_digest=hashlib.sha256(payload).hexdigest(),
        )
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        raise QuotaDenied("provider_source_statement_invalid") from exc
