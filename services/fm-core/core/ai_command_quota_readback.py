"""F3/P01 read-only evidence that a fresh Assistant grant matches Core's quota ledger.

Never reserves tokens or issues a license. Must be explicitly mounted behind
corporate S2S identity and TLS; unrelated tenant/browser traffic is untrusted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from core.ai_plan_usage_guard import PlanPolicyAuthority
from core.ai_quota_store import QuotaDenied, QuotaReservations

PATH = "/internal/v1/command/ai/quota-readback"
SCHEMA = "fm.core.ai.quota-readback.v1"
_LIMIT = 2048
_SCOPE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")
_CAPABILITIES = frozenset({"atendimento_interpretacao", "atendimento_transcricao"})


def _reject(status: int, reason: str):
    raise HTTPException(status_code=status, detail=reason)


def sign_command_quota_readback(*, secret: bytes, body: bytes) -> str:
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError("core_quota_readback.invalid_key")
    return hmac.new(secret, b"POST\n" + PATH.encode() + b"\n" + body, hashlib.sha256).hexdigest()


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def command_core_quota_readback_router(
    *, authority: PlanPolicyAuthority,
    quota: QuotaReservations, shared_secret: bytes,
) -> APIRouter:
    """Opt-in read port: no policy projection and no balance reservation."""
    if type(shared_secret) is not bytes or len(shared_secret) < 32:
        raise ValueError("core_quota_readback.invalid_key")
    router = APIRouter(prefix="/internal/v1/command", tags=["internal-quota"])

    @router.post("/ai/quota-readback")
    async def readback(
        request: Request,
        x_fm_command_quota_signature: str | None = Header(
            default=None, alias="X-FM-Command-Quota-Signature",
        ),
    ) -> JSONResponse:
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            _reject(415, "core_quota_readback.content_type")
        chunks = []
        size = 0
        async for part in request.stream():
            size += len(part)
            if size > _LIMIT:
                _reject(413, "core_quota_readback.body_too_large")
            chunks.append(part)
        raw = b"".join(chunks)
        if (
            not raw
            or not isinstance(x_fm_command_quota_signature, str)
            or re.fullmatch(r"[a-f0-9]{64}", x_fm_command_quota_signature) is None
            or not hmac.compare_digest(
                sign_command_quota_readback(secret=shared_secret, body=raw),
                x_fm_command_quota_signature,
            )
        ):
            _reject(401, "core_quota_readback.unauthorized")
        try:
            data = json.loads(raw, object_pairs_hook=_unique)
            if not isinstance(data, dict) or set(data) != {
                "schema", "tenant_id", "unit_id", "capability", "issued_at", "nonce",
            } or data["schema"] != SCHEMA:
                raise ValueError("invalid_schema")
            tenant, unit, capability = (data[k] for k in ("tenant_id", "unit_id", "capability"))
            if any(not isinstance(value, str) or not _SCOPE.fullmatch(value) for value in (tenant, unit)):
                raise ValueError("invalid_scope")
            if capability not in _CAPABILITIES or type(data["issued_at"]) is not int:
                raise ValueError("invalid_capability")
            if not isinstance(data["nonce"], str) or not _NONCE.fullmatch(data["nonce"]):
                raise ValueError("invalid_nonce")
            now = datetime.now(UTC)
            if abs(int(now.timestamp()) - data["issued_at"]) > 30:
                raise ValueError("stale_request")
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            raise HTTPException(400, "core_quota_readback.invalid_request") from exc

        # This call MUST authenticate Assistant afresh: no cached grants, no
        # browser-supplied plan/limits, no quota reservation as a side effect.
        try:
            policy = authority.resolve(
                tenant_id=tenant, unit_id=unit, capability=capability, now=now,
            )
        except (QuotaDenied, Exception) as exc:
            raise HTTPException(409, "core_quota_readback.license_unverified") from exc
        if policy.tenant_id != tenant or policy.unit_id != unit or policy.valid_until <= now:
            _reject(409, "core_quota_readback.license_unverified")

        results: list[dict[str, object]] = []
        try:
            for metric, scope, limit, window in policy.grants:
                unit_key = "__tenant__" if scope == "tenant" else unit
                snap = quota.usage_snapshot(
                    tenant_id=tenant, unit_id=unit_key, capability=metric, at=now,
                )
                if (snap.policy_revision != policy.revision or
                    snap.limit_units != limit or snap.window_seconds != window or
                    snap.reserved_units + snap.consumed_units + snap.remaining_units != limit):
                    _reject(409, "core_quota_readback.policy_mismatch")
                results.append({
                    "metric": metric, "scope": scope,
                    "limit_units": limit, "window_seconds": window,
                    "reserved_units": snap.reserved_units,
                    "consumed_units": snap.consumed_units,
                    "remaining_units": snap.remaining_units,
                    "policy_revision": snap.policy_revision,
                })
        except QuotaDenied as exc:
            # No projection yet: this is NOT evidence of zero spend, and must
            # not project grants or reserve a synthetic request.
            raise HTTPException(409, "core_quota_readback.policy_not_projected") from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "core_quota_readback.ledger_unavailable") from exc
        if not results or not {"ai.requests", "ai.total_tokens"}.issubset(
            {row["metric"] for row in results}
        ):
            _reject(409, "core_quota_readback.policy_incomplete")
        return JSONResponse({
            "schema": SCHEMA, "tenant_id": tenant, "unit_id": unit,
            "capability": capability, "plan_code": policy.plan_code,
            "plan_revision": policy.revision,
            "grant_expires_at": int(policy.valid_until.timestamp()),
            "license_freshly_verified": True,
            "core_policy_matches_signed_grant": True,
            "quota_metrics": results,
            "reservation_created": False, "provider_called": False,
            "case_resolved": False,
        }, headers={"Cache-Control": "no-store"})

    return router
