"""Canonical plan quota snapshot derived from a licensed Assistant tenant.

This is a read-only projection. Core must receive it only over a separately
authenticated service channel with revocation/freshness checks before use.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db import PlanLimitORM
from .plan_limits import PlanLimitDenied, PlanLimitResolver


@dataclass(frozen=True, kw_only=True)
class PlanQuotaGrant:
    resource: str
    scope: str
    limit_units: int
    window_seconds: int


@dataclass(frozen=True, kw_only=True)
class LicensedQuotaManifest:
    tenant_id: str
    unit_id: str
    plan_code: str
    revision: int
    licensed_until: datetime
    grants: tuple[PlanQuotaGrant, ...]

    def policy_fingerprint(self) -> tuple:
        return (
            self.plan_code, self.revision,
            tuple((x.resource, x.scope, x.limit_units, x.window_seconds)
                  for x in self.grants),
        )


class LicensedQuotaManifestService:
    """Fail closed when plan/license, grants or scope is inconsistent."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions
        self._resolver = PlanLimitResolver(sessions)

    def resolve(
        self, *, tenant_id: str, unit_id: str, now: datetime,
    ) -> LicensedQuotaManifest:
        ref = self._resolver.resolve(
            tenant_id=tenant_id, unit_id=unit_id,
            resource="ai.requests", now=now,
        )
        token_ref = self._resolver.resolve(
            tenant_id=tenant_id, unit_id=unit_id,
            resource="ai.total_tokens", now=now,
        )
        if (ref.plan_code, ref.revision, ref.licensed_until) != (
            token_ref.plan_code, token_ref.revision, token_ref.licensed_until,
        ):
            raise PlanLimitDenied("plan.mixed_authority")
        with self._sessions() as db:
            records = db.scalars(
                select(PlanLimitORM).where(
                    PlanLimitORM.plan_code == ref.plan_code,
                    PlanLimitORM.revision == ref.revision,
                ).order_by(PlanLimitORM.resource),
            ).all()
            grants = tuple(PlanQuotaGrant(
                resource=record.resource, scope=record.scope,
                limit_units=record.limit_units,
                window_seconds=record.window_seconds,
            ) for record in records)
        if (
            len(grants) < 2
            or not {"ai.requests", "ai.total_tokens"}.issubset(
                {grant.resource for grant in grants}
            )
            or any(
                grant.scope not in {"tenant", "unit"}
                or grant.limit_units <= 0 or grant.window_seconds <= 0
                for grant in grants
            )
        ):
            raise PlanLimitDenied("plan.grants_incomplete")
        return LicensedQuotaManifest(
            tenant_id=tenant_id, unit_id=unit_id,
            plan_code=ref.plan_code, revision=ref.revision,
            licensed_until=ref.licensed_until, grants=grants,
        )


# Signed read-through grant for the Core. Only a trusted, authenticated
# service route may invoke this issuer; never expose the signing key to tenants.
def issue_core_plan_grant(
    *, manifest: LicensedQuotaManifest, capability: str,
    input_bound: int, output_bound: int, secret: bytes, now: datetime,
    challenge: str,
) -> tuple[bytes, str]:
    if (
        not isinstance(challenge, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{22,96}", challenge) is None
        or not isinstance(secret, bytes) or len(secret) < 32
        or now.tzinfo is None or now.utcoffset() is None
        or manifest.licensed_until.tzinfo is None
        or manifest.licensed_until.utcoffset() is None
        or manifest.licensed_until <= now
        or not isinstance(capability, str) or not 0 < len(capability) <= 128
        or type(input_bound) is not int or type(output_bound) is not int
        or input_bound <= 0 or output_bound <= 0
        or input_bound + output_bound > 2_000_000_000
    ):
        raise PlanLimitDenied("plan.grant_denied")
    grants = {g.resource: g for g in manifest.grants}
    if len(grants) != len(manifest.grants) or not {
        "ai.requests", "ai.total_tokens",
    }.issubset(grants):
        raise PlanLimitDenied("plan.grant_metrics_invalid")
    if input_bound + output_bound > grants["ai.total_tokens"].limit_units:
        raise PlanLimitDenied("plan.grant_bounds_exceeded")
    for metric, bound in (
        ("ai.input_tokens", input_bound),
        ("ai.output_tokens", output_bound),
    ):
        if metric in grants and bound > grants[metric].limit_units:
            raise PlanLimitDenied("plan.grant_bounds_exceeded")
    allowed = {
        "ai.requests", "ai.total_tokens", "ai.input_tokens",
        "ai.output_tokens", "ai.cached_tokens",
    }
    scopes = sorted([
        [g.resource, g.scope] for g in manifest.grants if g.resource in allowed
    ])
    if any(scope not in {"tenant", "unit"} for _, scope in scopes):
        raise PlanLimitDenied("plan.grant_scope_invalid")
    expiry = min(manifest.licensed_until, now + timedelta(seconds=30))
    body = json.dumps({
        "tenant_id": manifest.tenant_id,
        "unit_id": manifest.unit_id,
        "capability": capability,
        "challenge": challenge,
        "plan_code": manifest.plan_code,
        "revision": manifest.revision,
        "expires_at": int(expiry.timestamp()),
        "licensed_until": int(manifest.licensed_until.timestamp()),
        "input_bound": input_bound, "output_bound": output_bound,
        "scopes": scopes,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return body, hmac.new(
        secret, b"/internal/v1/assistant/core-plan-grant\n" + body,
        hashlib.sha256,
    ).hexdigest()


def authenticated_core_plan_grant(
    *, raw_body: bytes, request_signature: str | None,
    secret: str | None, sessions: sessionmaker[Session], now: datetime,
) -> tuple[bytes, str]:
    """Internal service-only request; always resolves live canonical license.

    The caller must enforce HTTPS and private service networking. No tenant
    session, browser cookie or client-supplied plan revision is an authority.
    """
    if (
        not secret or len(secret) < 32
        or not isinstance(raw_body, bytes) or len(raw_body) > 2048
        or not isinstance(request_signature, str)
        or re.fullmatch(r"[0-9a-f]{64}", request_signature) is None
        or now.tzinfo is None or now.utcoffset() is None
    ):
        raise PlanLimitDenied("plan.grant_denied")
    signing_key = secret.encode("utf-8")
    expected = hmac.new(
        signing_key,
        b"POST\n/internal/v1/assistant/core-plan-grant\n" + raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, request_signature):
        raise PlanLimitDenied("plan.grant_denied")
    try:
        body = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PlanLimitDenied("plan.grant_denied") from exc
    if not isinstance(body, dict) or set(body) != {
        "tenant_id", "unit_id", "capability", "challenge",
        "input_bound", "output_bound", "requested_at",
    }:
        raise PlanLimitDenied("plan.grant_denied")
    requested_at = body["requested_at"]
    if (
        type(requested_at) is not int
        or abs(int(now.timestamp()) - requested_at) > 30
        or not all(
            isinstance(body[key], str) and
            re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", body[key]) is not None
            for key in ("tenant_id", "unit_id", "capability")
        )
    ):
        raise PlanLimitDenied("plan.grant_denied")
    manifest = LicensedQuotaManifestService(sessions).resolve(
        tenant_id=body["tenant_id"], unit_id=body["unit_id"], now=now,
    )
    return issue_core_plan_grant(
        manifest=manifest, capability=body["capability"],
        input_bound=body["input_bound"], output_bound=body["output_bound"],
        secret=signing_key, now=now, challenge=body["challenge"],
    )
