"""Validate Assistant live-license signed quota snapshot before Core mutation.

A trusted Core service obtains the snapshot using authenticated challenge
request to Assistant; caller validates response signature and exact scope.
The snapshot is short-lived, and Core's canonical quota ledger fences versions.
This module is not a browser/tenant-facing privilege escalation endpoint.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from core.ai_quota_store import QuotaDenied, QuotaReservations

_SCOPE = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
_NONCE = re.compile(r"[A-Za-z0-9_-]{22,96}\Z")


@dataclass(frozen=True, kw_only=True)
class ExpectedLicensedScope:
    tenant_id: str
    unit_id: str
    capability: str
    challenge: str


def apply_authenticated_license_grant(
    *, payload: bytes, signature: str,
    key: bytes, expected: ExpectedLicensedScope,
    ledger: QuotaReservations, at: datetime,
) -> tuple[int, int, int]:
    """Project confirmed license grants only; return revision and token bounds.

    Revalidating the current license and issuing the signature is Assistant's
    responsibility. Revocation must force a new grant challenge on every
    execution. Old cached grants must never authorize execution.
    """
    if (
        not isinstance(payload, bytes) or not 1 <= len(payload) <= 10000
        or not isinstance(signature, str) or re.fullmatch(r"[a-f0-9]{64}", signature) is None
        or not isinstance(key, bytes) or len(key) < 32
        or not isinstance(at, datetime) or at.tzinfo is None
        or any(
            not isinstance(v, str) or _SCOPE.fullmatch(v) is None
            for v in (expected.tenant_id, expected.unit_id, expected.capability)
        )
        or not isinstance(expected.challenge, str)
        or _NONCE.fullmatch(expected.challenge) is None
    ):
        raise QuotaDenied("core_license_grant_invalid")
    anticipated = hmac.new(
        key, b"/internal/v1/assistant/core-plan-grant\n" + payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(anticipated, signature):
        raise QuotaDenied("core_license_grant_signature_invalid")
    try:
        d = json.loads(payload)
        fields = {
            "tenant_id", "unit_id", "capability", "challenge",
            "plan_code", "revision", "expires_at", "licensed_until",
            "input_bound", "output_bound", "scopes", "grants",
        }
        if not isinstance(d, dict) or set(d) != fields:
            raise ValueError("shape")
        if tuple(d[k] for k in (
            "tenant_id", "unit_id", "capability", "challenge",
        )) != (
            expected.tenant_id, expected.unit_id,
            expected.capability, expected.challenge,
        ):
            raise ValueError("scope")
        if (
            not isinstance(d["plan_code"], str)
            or _SCOPE.fullmatch(d["plan_code"]) is None
            or any(type(d[k]) is not int for k in (
                "revision", "expires_at", "licensed_until",
                "input_bound", "output_bound",
            ))
            or d["revision"] < 1
            or d["input_bound"] <= 0 or d["output_bound"] <= 0
            or d["input_bound"] + d["output_bound"] > 2_000_000_000
            or not isinstance(d["grants"], list)
            or not 2 <= len(d["grants"]) <= 5
        ):
            raise ValueError("fields")
        now = int(at.astimezone(UTC).timestamp())
        if (
            d["expires_at"] <= now
            or d["expires_at"] > now + 30
            or d["licensed_until"] <= now
            or d["expires_at"] > d["licensed_until"]
        ):
            raise ValueError("expiry")
        grants = []
        scope_info = []
        for entry in d["grants"]:
            if (
                not isinstance(entry, list) or len(entry) != 4
                or not isinstance(entry[0], str)
                or entry[1] not in ("tenant", "unit")
                or any(type(v) is not int for v in entry[2:])
                or entry[2] <= 0 or entry[3] <= 0
            ):
                raise ValueError("grant")
            grants.append(tuple(entry))
            scope_info.append([entry[0], entry[1]])
        if (
            len({x[0] for x in grants}) != len(grants)
            or sorted(scope_info) != d["scopes"]
            or not {"ai.requests", "ai.total_tokens"}.issubset(
                {x[0] for x in grants}
            )
        ):
            raise ValueError("metrics")
    except (ValueError, TypeError, KeyError) as exc:
        raise QuotaDenied("core_license_grant_payload_invalid") from exc
    ledger.project_signed_grants(
        tenant_id=expected.tenant_id, unit_id=expected.unit_id,
        revision=d["revision"], grants=tuple(grants),
    )
    return d["revision"], d["input_bound"], d["output_bound"]


def reserve_licensed_ai_attempt(
    *, payload: bytes, signature: str, key: bytes,
    expected: ExpectedLicensedScope, ledger: QuotaReservations,
    at: datetime, request_id: str, input_budget: int, output_budget: int,
) -> None:
    """Authorize *this* execution only with a fresh Assistant grant.

    Never authorize from a previously projected policy alone; an expired
    license, absent signature, replayed request or exceeded budget fails
    before any provider call. The existing ledger reserves atomically.
    """
    from core.ai_quota_store import QuotaRequirement

    if (
        type(input_budget) is not int or type(output_budget) is not int
        or input_budget <= 0 or output_budget <= 0
    ):
        raise QuotaDenied("core_license_budget_invalid")
    # Authentication precedes all side effects.
    revision, input_limit, output_limit = apply_authenticated_license_grant(
        payload=payload, signature=signature, key=key,
        expected=expected, ledger=ledger, at=at,
    )
    if input_budget > input_limit or output_budget > output_limit:
        raise QuotaDenied("core_license_budget_exceeded")
    body = json.loads(payload)
    scopes = {g[0]: g[1] for g in body["grants"]}
    required = []
    for metric, units in (
        ("ai.requests", 1),
        ("ai.total_tokens", input_budget + output_budget),
        ("ai.input_tokens", input_budget),
        ("ai.output_tokens", output_budget),
    ):
        if metric in scopes:
            required.append(QuotaRequirement(
                tenant_id=expected.tenant_id,
                unit_id="__tenant__" if scopes[metric] == "tenant" else expected.unit_id,
                capability=metric, units=units, policy_revision=revision,
            ))
    ledger.reserve_bundle(needs=tuple(required), request_id=request_id, at=at)
