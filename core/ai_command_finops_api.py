"""F9: optional authenticated Command read port for Core-owned AI FinOps.

Never mounts automatically, never accesses provider credentials, and never
converts an unobserved/unknown cost into certified zero. A report aggregates
the existing immutable Core usage events; commercial prices remain in Command.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from core.ai_finops import AIFinOpsBucket

PATH = "/internal/v1/command/ai/finops/report"
SCHEMA = "fm.core.finops.read.v1"
_SCOPE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")
_MAX_AGE_SECONDS = 30
_MAX_DAYS = 31
_MAX_BODY = 2048
_MAX_BUCKETS = 500


class FinOpsReadPort(Protocol):
    def listar(
        self, *, tenant_id: str, unidade_id: str, inicio: date, fim: date,
    ) -> tuple[AIFinOpsBucket, ...]: ...


def sign_finops_request(*, secret: bytes, raw_body: bytes) -> str:
    """Stable HMAC over METHOD, literal path and exact request bytes."""
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError("core_finops.transport_key_invalid")
    return hmac.new(
        secret, b"POST\n" + PATH.encode() + b"\n" + raw_body, hashlib.sha256,
    ).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _read_scope(raw_body: bytes, at: datetime) -> tuple[str, str, date, date]:
    try:
        data = json.loads(raw_body, object_pairs_hook=_no_duplicate_keys)
        if not isinstance(data, dict) or set(data) != {
            "schema", "tenant_id", "unit_id", "start_date", "end_date",
            "issued_at", "nonce",
        }:
            raise ValueError("invalid_shape")
        if data["schema"] != SCHEMA:
            raise ValueError("invalid_schema")
        for name in ("tenant_id", "unit_id"):
            value = data[name]
            if not isinstance(value, str) or _SCOPE.fullmatch(value) is None:
                raise ValueError("invalid_scope")
        if not isinstance(data["nonce"], str) or _NONCE.fullmatch(data["nonce"]) is None:
            raise ValueError("invalid_nonce")
        timestamp = data["issued_at"]
        if type(timestamp) is not int or abs(int(at.timestamp()) - timestamp) > _MAX_AGE_SECONDS:
            raise ValueError("stale_request")
        for name in ("start_date", "end_date"):
            value = data[name]
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("invalid_date")
        start = date.fromisoformat(data["start_date"])
        end = date.fromisoformat(data["end_date"])
        if end < start or (end - start).days >= _MAX_DAYS or end > at.date():
            raise ValueError("invalid_period")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail="core_finops.invalid_request") from exc
    return data["tenant_id"], data["unit_id"], start, end


def _bucket_projection(bucket: AIFinOpsBucket, tenant_id: str, unit_id: str,
                       start: date, end: date) -> dict[str, object]:
    if (
        bucket.tenant_id != tenant_id or bucket.unidade_id != unit_id
        or not start <= bucket.bucket_date <= end
        or bucket.cost_known_events + bucket.cost_unknown_events != bucket.attempts
        or bucket.fallback_attempts > bucket.attempts
        or not isinstance(bucket.cost_total, Decimal)
        or not bucket.cost_total.is_finite() or bucket.cost_total < 0
    ):
        raise ValueError("core_finops.ledger_inconsistent")
    # Never round money with binary floating point. A subtotal is not the
    # actual invoiced spend. It excludes attempts with unknown costs.
    return {
        "day": bucket.bucket_date.isoformat(),
        "provider": bucket.provider,
        "model": bucket.model,
        "capability": bucket.capability,
        "outcome": bucket.outcome,
        "currency": bucket.moeda,
        "attempts": bucket.attempts,
        "fallback_attempts": bucket.fallback_attempts,
        "input_tokens_observed": bucket.input_tokens,
        "output_tokens_observed": bucket.output_tokens,
        "cached_tokens_observed": bucket.cached_tokens,
        "token_counters_complete": False,
        "latency_ms_total": bucket.latency_ms_total,
        "latency_ms_max": bucket.latency_ms_max,
        "known_cost_events": bucket.cost_known_events,
        "unknown_cost_events": bucket.cost_unknown_events,
        "known_cost_subtotal": str(bucket.cost_total),
        "actual_provider_spend_verified": False,
    }


def command_finops_router(*, read_model: FinOpsReadPort,
                          shared_secret: bytes) -> APIRouter:
    """Read-only, disabled unless explicitly mounted with isolated S2S key.

    Production ingress MUST additionally enforce TLS, network allowlists,
    rate limits and corporate Command identity before calling this endpoint.
    Raw client/browser requests must never be forwarded as trusted Command.
    """
    if type(shared_secret) is not bytes or len(shared_secret) < 32:
        raise ValueError("core_finops.transport_key_invalid")
    router = APIRouter(prefix="/internal/v1/command", tags=["internal-finops"])

    @router.post("/ai/finops/report")
    async def report(
        request: Request,
        x_fm_command_finops_signature: str | None = Header(
            default=None, alias="X-FM-Command-FinOps-Signature",
        ),
    ) -> JSONResponse:
        now = datetime.now(UTC)
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise HTTPException(status_code=415, detail="core_finops.invalid_content_type")
        if request.headers.get("content-length") is not None:
            try:
                if int(request.headers["content-length"]) > _MAX_BODY:
                    raise HTTPException(status_code=413, detail="core_finops.body_too_large")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="core_finops.invalid_request") from exc
        # Stream with an absolute byte ceiling: Transfer-Encoding: chunked or
        # missing Content-Length must not cause unbounded memory allocation.
        total = 0
        chunks: list[bytes] = []
        async for chunk in request.stream():
            total += len(chunk)
            if total > _MAX_BODY:
                raise HTTPException(status_code=413, detail="core_finops.body_too_large")
            chunks.append(chunk)
        body = b"".join(chunks)
        if not body:
            raise HTTPException(status_code=400, detail="core_finops.invalid_request")
        if (
            not isinstance(x_fm_command_finops_signature, str)
            or re.fullmatch(r"[a-f0-9]{64}", x_fm_command_finops_signature) is None
            or not hmac.compare_digest(
                sign_finops_request(secret=shared_secret, raw_body=body),
                x_fm_command_finops_signature,
            )
        ):
            raise HTTPException(status_code=401, detail="core_finops.unauthorized")
        tenant_id, unit_id, start, end = _read_scope(body, now)
        try:
            buckets = read_model.listar(
                tenant_id=tenant_id, unidade_id=unit_id, inicio=start, fim=end,
            )
            if len(buckets) > _MAX_BUCKETS:
                raise ValueError("core_finops.too_many_buckets")
            items = [
                _bucket_projection(bucket, tenant_id, unit_id, start, end)
                for bucket in buckets
            ]
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(
                status_code=409, detail="core_finops.ledger_unavailable",
            ) from exc
        except Exception as exc:
            # Database outage, serialization error or unavailable internal
            # source cannot silently become an empty/zero spend report.
            raise HTTPException(
                status_code=503, detail="core_finops.source_unavailable",
            ) from exc
        # No global sum of differently denominated currencies, and no claim
        # that an empty ledger proves that nothing was charged.
        return JSONResponse(
            {
                "schema": SCHEMA,
                "tenant_id": tenant_id,
                "unit_id": unit_id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "buckets": items,
                "known_attempts": sum(x["known_cost_events"] for x in items),
                "unknown_attempts": sum(x["unknown_cost_events"] for x in items),
                "coverage": (
                    "no_observations" if not items else
                    "partial_unknown_costs" if any(x["unknown_cost_events"] for x in items) else
                    "priced_internal_observations"
                ),
                "internal_fm_cost_only": True,
                "actual_provider_spend_verified": False,
                "commercial_revenue_included": False,
            },
            headers={"Cache-Control": "no-store"},
        )

    return router
