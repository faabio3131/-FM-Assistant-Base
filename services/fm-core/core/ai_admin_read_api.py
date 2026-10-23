"""Read-only technical operations API, separate from consumer credentials.

This is NOT a human platform_admin authority. Until a signed Command identity
and governed admin mutation/audit policy exist, no write API is exposed.
"""

from __future__ import annotations

import hmac
import json
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import (
    AIControlPlaneStore,
    AIProvider,
    AIProviderHealth,
    ControlPlaneError,
)
from core.ai_finops_alert_outbox import PersistentFinOpsAlertOutbox
from core.ai_finops_alerts import evaluate_request_cost_alert
from core.ai_finops_policy_store import PersistentFinOpsAlertPolicies
from core.ai_provider_export_store import PersistentProviderExportStore
from core.ai_router import CapabilityIA
from core.ai_usage_ledger import AIUsageRecord, PersistentAIFinOps, _observed_cost


def require_operator_key(
    request: Request,
    x_core_admin_key: str | None = Header(default=None, alias="X-Core-Admin-Key"),
) -> None:
    cfg = request.app.state.settings
    if not cfg.persistent_control_plane or not cfg.admin_key:
        raise HTTPException(status_code=404, detail="core_operator_api_disabled")
    if not x_core_admin_key or not hmac.compare_digest(cfg.admin_key, x_core_admin_key):
        raise HTTPException(status_code=401, detail="core_operator_unauthorized")


def _sessions(request: Request):
    engine = request.app.state.control_plane_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="core_control_plane_not_ready")
    return sessionmaker(engine, expire_on_commit=False)


def register_admin_read_routes(app: FastAPI) -> None:
    router = APIRouter(
        prefix="/v1/admin/ai",
        tags=["internal-core-operator-readonly"],
        dependencies=[Depends(require_operator_key)],
    )

    @router.get("/providers/health")
    def provider_health(request: Request) -> list[dict[str, str | bool]]:
        try:
            with _sessions(request)() as db:
                records = db.execute(
                    select(AIProvider, AIProviderHealth)
                    .outerjoin(
                        AIProviderHealth, AIProvider.provider_id == AIProviderHealth.provider_id
                    )
                    .order_by(AIProvider.provider_id)
                    .limit(1000)
                ).all()
                return [
                    {
                        "provider_id": provider.provider_id,
                        "enabled": provider.enabled,
                        "health": state.status if state is not None else "unknown",
                        "circuit": state.circuit if state is not None else "unknown",
                    }
                    for provider, state in records
                ]
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="core_operator_query_unavailable") from exc

    @router.get("/routes")
    def resolved_routes(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        capability: CapabilityIA = CapabilityIA.ATENDIMENTO_INTERPRETACAO,
    ) -> list[dict[str, str | int]]:
        try:
            routes = AIControlPlaneStore(_sessions(request)).resolve(
                tenant_id=tenant_id, unit_id=unit_id, capability=capability
            )
        except (ControlPlaneError, SQLAlchemyError) as exc:
            raise HTTPException(status_code=503, detail="core_operator_route_unavailable") from exc
        return [
            {
                "policy_id": item.route.configuracao_id,
                "scope": item.scope,
                "provider": item.route.provider,
                "model": item.route.model,
                "priority": item.route.prioridade,
                "price_snapshot_id": item.route.price_snapshot_id,
            }
            for item in routes
        ]

    @router.get("/usage")
    def usage(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        start_date: date = Query(),
        end_date: date = Query(),
    ) -> list[dict[str, str | int]]:
        try:
            buckets = PersistentAIFinOps(_sessions(request)).listar(
                tenant_id=tenant_id,
                unidade_id=unit_id,
                inicio=start_date,
                fim=end_date,
            )
        except (ControlPlaneError, SQLAlchemyError) as exc:
            raise HTTPException(status_code=422, detail="core_operator_usage_invalid") from exc
        return [
            {
                "day": item.bucket_date.isoformat(),
                "provider": item.provider,
                "model": item.model,
                "capability": item.capability,
                "outcome": item.outcome,
                "currency": item.moeda,
                "attempts": item.attempts,
                "fallback_attempts": item.fallback_attempts,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "cost_known_events": item.cost_known_events,
                "cost_unknown_events": item.cost_unknown_events,
                "cost_total": str(item.cost_total),
            }
            for item in buckets
        ]

    @router.get("/usage/attempts")
    def usage_physical_attempts(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        request_id: str = Query(min_length=1, max_length=128),
    ) -> JSONResponse:
        """Operator's bounded physical attempts, including fallbacks."""
        try:
            with _sessions(request)() as db:
                rows = db.scalars(select(AIUsageRecord).where(
                    AIUsageRecord.tenant_id == tenant_id,
                    AIUsageRecord.unit_id == unit_id,
                    AIUsageRecord.request_id == request_id,
                ).order_by(AIUsageRecord.event_time, AIUsageRecord.event_id)
                    .limit(101)).all()
                if len(rows) > 100:
                    raise ControlPlaneError("core_finops.attempts_unbounded")
                items = [{
                    "event_id": row.event_id,
                    "attempt_id": row.attempt_id,
                    "provider": row.provider,
                    "model": row.model,
                    "outcome": row.outcome,
                    "fallback": bool(row.fallback_used),
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "cost_known_subtotal_usd": (
                        str(_observed_cost(row.cost_decimal))
                        if row.cost_decimal is not None and row.currency == "USD"
                        else None
                    ),
                    "cost_known": row.cost_decimal is not None,
                } for row in rows]
        except ControlPlaneError as exc:
            raise HTTPException(
                status_code=422, detail="core_finops.attempts_invalid",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.attempts_unavailable",
            ) from exc
        return JSONResponse({
            "tenant_id": tenant_id, "unit_id": unit_id,
            "request_id": request_id, "items": items,
            "provider_invoice_verified": False,
        }, headers={"Cache-Control": "no-store"})

    @router.get("/usage/provider-export/coverage")
    def provider_export_coverage(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        start_date: date = Query(),
        end_date: date = Query(),
        page: int = Query(default=0, ge=0, le=20000),
        limit: int = Query(default=50, ge=1, le=100),
        only_missing: bool = False,
    ) -> JSONResponse:
        """Inventory physical attempts, missing exports and mismatches."""
        try:
            result = PersistentProviderExportStore(_sessions(request)).coverage(
                tenant_id=tenant_id, unit_id=unit_id,
                start_date=start_date, end_date=end_date,
                page=page, limit=limit, only_missing=only_missing,
            )
        except ControlPlaneError as exc:
            raise HTTPException(
                status_code=422, detail="core_finops.export_coverage_invalid",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.export_coverage_unavailable",
            ) from exc
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @router.get("/usage/provider-export")
    def provider_export_comparison(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        request_id: str = Query(min_length=1, max_length=128),
        attempt_id: str = Query(min_length=1, max_length=128),
    ) -> JSONResponse:
        """Scoped FM drilldown. Unknown and missing exports stay actionable."""
        try:
            result = PersistentProviderExportStore(_sessions(request)).compare(
                tenant_id=tenant_id, unit_id=unit_id,
                request_id=request_id, attempt_id=attempt_id,
            )
        except ControlPlaneError as exc:
            raise HTTPException(
                status_code=422, detail="core_finops.export_read_invalid",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.export_unavailable",
            ) from exc
        return JSONResponse({
            "tenant_id": tenant_id, "unit_id": unit_id,
            "request_id": request_id, "attempt_id": attempt_id,
            "status": result.status if result else "missing_provider_export",
            "provider": result.provider if result else None,
            "source_ref": result.source_ref if result else None,
            "input_tokens_reported": result.input_tokens_reported if result else None,
            "output_tokens_reported": result.output_tokens_reported if result else None,
            "report_cost_usd": (
                str(result.report_cost_usd)
                if result and result.report_cost_usd is not None else None
            ),
            "internal_cost_usd": (
                str(result.internal_cost_usd)
                if result and result.internal_cost_usd is not None else None
            ),
            "usage_matches": result.usage_matches if result else None,
            "cost_matches": result.cost_matches if result else None,
            "needs_attention": result.needs_attention if result else True,
            "provider_invoice_verified": False,
            "provider_signature_verified": False,
            "quota_recovery_authorized": False,
        }, headers={"Cache-Control": "no-store"})

    @router.get("/usage/pending")
    def pending_usage_reconciliation(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        start_date: date = Query(),
        end_date: date = Query(),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> JSONResponse:
        """FM operator-only queue; observations do not attest provider invoices."""
        try:
            items, truncated = PersistentAIFinOps(_sessions(request)).listar_pendencias(
                tenant_id=tenant_id, unit_id=unit_id,
                inicio=start_date, fim=end_date, limit=limit,
            )
        except ControlPlaneError as exc:
            raise HTTPException(
                status_code=422, detail="core_operator_pending_scope_invalid",
            ) from exc
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=503, detail="core_operator_pending_unavailable",
            ) from exc
        return JSONResponse(
            {
                "tenant_id": tenant_id, "unit_id": unit_id,
                "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
                "status": "needs_attention" if items else "no_pending_observations",
                "truncated": truncated,
                "provider_invoice_verified": False,
                "items": [
                    {
                        "request_id": item.request_id,
                        "first_seen": item.first_seen.isoformat(),
                        "last_seen": item.last_seen.isoformat(),
                        "observed_attempts": item.observed_attempts,
                        "unknown_cost_attempts": item.unknown_cost_attempts,
                        "incomplete_token_attempts": item.incomplete_token_attempts,
                        "fallback_attempts": item.fallback_attempts,
                    }
                    for item in items
                ],
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/usage/alerts")
    def list_finops_alerts(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        start_date: date = Query(),
        end_date: date = Query(),
        limit: int = Query(default=50, ge=1, le=100),
        after_request_id: str | None = Query(default=None, min_length=1, max_length=128),
    ) -> JSONResponse:
        """FM-only bounded alert inbox. No provider invoice proof or quota mutation."""
        try:
            sessions = _sessions(request)
            policy = PersistentFinOpsAlertPolicies(sessions).get(
                tenant_id=tenant_id, unit_id=unit_id,
            )
            store = PersistentAIFinOps(sessions)
            ids, next_cursor = store.listar_ids_solicitacoes(
                tenant_id=tenant_id, unit_id=unit_id,
                inicio=start_date, fim=end_date,
                after_request_id=after_request_id, limit=limit,
            )
            items = []
            for request_id in ids:
                alert = evaluate_request_cost_alert(
                    store.reconcile_request(
                        tenant_id=tenant_id, unit_id=unit_id, request_id=request_id,
                    ),
                    maximum_known_cost=(
                        policy.maximum_known_cost if policy and policy.enabled else None
                    ),
                    currency=policy.currency if policy and policy.enabled else None,
                )
                items.append({
                    "request_id": request_id,
                    "status": alert.status, "reasons": list(alert.reasons),
                    "known_cost_subtotal": str(alert.known_cost),
                    "currency": alert.cost_currency,
                    "unknown_attempts": alert.unknown_attempts,
                    "observed_attempts": alert.observed_attempts,
                    "all_recorded_costs_known": alert.all_costs_known,
                    "provider_invoice_verified": False,
                })
        except (ControlPlaneError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="core_finops.alert_inbox_invalid",
            ) from exc
        except (SQLAlchemyError, TypeError, ArithmeticError) as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.alert_inbox_unavailable",
            ) from exc
        return JSONResponse({
            "tenant_id": tenant_id, "unit_id": unit_id,
            "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
            "policy_revision": policy.revision if policy else None,
            "policy_enabled": policy.enabled if policy else False,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
            "provider_invoice_verified": False,
            "items": items,
        }, headers={"Cache-Control": "no-store"})

    @router.get("/usage/alerts/outbox")
    def pending_finops_outbox(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        limit: int = Query(default=50, ge=1, le=100),
        after_event_id: str | None = Query(
            default=None, pattern=r"^[0-9a-f]{64}$",
        ),
    ) -> JSONResponse:
        """Read persisted FM-owned alerts; no claim of provider invoice proof."""
        try:
            page = PersistentFinOpsAlertOutbox(_sessions(request)).page_pending(
                tenant_id=tenant_id, unit_id=unit_id, limit=limit,
                after_event_id=after_event_id,
            )
        except ControlPlaneError as exc:
            raise HTTPException(
                status_code=422, detail="core_finops.alert_outbox_invalid",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.alert_outbox_unavailable",
            ) from exc
        return JSONResponse({
            "tenant_id": tenant_id, "unit_id": unit_id,
            "status": "pending_review" if page.items else "no_queued_alerts",
            "provider_invoice_verified": False,
            "automated_dispatch_enabled": False,
            "next_cursor": page.next_cursor,
            "items": [
                {
                    "event_id": row.event_id,
                    "request_id": row.request_id,
                    "policy_revision": row.policy_revision,
                    "reasons": json.loads(row.reasons_json),
                    "known_cost_subtotal": row.known_cost_subtotal,
                    "currency": row.currency,
                    "unknown_attempts": row.unknown_attempts,
                    "observed_attempts": row.observed_attempts,
                    "created_at": row.created_at.isoformat(),
                }
                for row in page.items
            ],
        }, headers={"Cache-Control": "no-store"})

    @router.get("/finops/alert-policy")
    def read_finops_alert_policy(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
    ) -> JSONResponse:
        try:
            policy = PersistentFinOpsAlertPolicies(_sessions(request)).get(
                tenant_id=tenant_id, unit_id=unit_id,
            )
        except ControlPlaneError as exc:
            raise HTTPException(status_code=422, detail="core_finops.alert_scope_invalid") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="core_finops.alert_unavailable") from exc
        return JSONResponse({
            "tenant_id": tenant_id, "unit_id": unit_id,
            "configured": policy is not None,
            "revision": policy.revision if policy else None,
            "enabled": policy.enabled if policy else False,
            "currency": policy.currency if policy else None,
            "maximum_known_cost": str(policy.maximum_known_cost) if policy else None,
        }, headers={"Cache-Control": "no-store"})

    @router.get("/usage/request")
    def request_finops_alert(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        request_id: str = Query(min_length=1, max_length=128),
        maximum_known_cost: Decimal | None = Query(default=None, gt=0),
        currency: str | None = Query(default=None, min_length=3, max_length=3),
    ) -> dict[str, object]:
        """Pure operator read: unknown cost remains UNKNOWN, not accounting zero."""
        try:
            sessions = _sessions(request)
            policy = PersistentFinOpsAlertPolicies(sessions).get(
                tenant_id=tenant_id, unit_id=unit_id,
            )
            # A caller cannot override or bypass FM's persisted policy.
            if policy is not None and (
                maximum_known_cost is not None or currency is not None
            ):
                raise ValueError("finops.alert_override_denied")
            summary = PersistentAIFinOps(sessions).reconcile_request(
                tenant_id=tenant_id, unit_id=unit_id, request_id=request_id,
            )
            alert = evaluate_request_cost_alert(
                summary,
                maximum_known_cost=(
                    policy.maximum_known_cost if policy and policy.enabled
                    else maximum_known_cost
                ),
                currency=(
                    policy.currency if policy and policy.enabled else currency
                ),
            )
        except (ControlPlaneError, SQLAlchemyError) as exc:
            raise HTTPException(
                status_code=503, detail="core_operator_usage_unavailable",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="core_operator_alert_policy_invalid",
            ) from exc
        return {
            "tenant_id": tenant_id, "unit_id": unit_id,
            "request_id": request_id,
            "status": alert.status,
            "reasons": list(alert.reasons),
            "known_cost_subtotal": str(alert.known_cost),
            "currency": alert.cost_currency,
            "unknown_attempts": alert.unknown_attempts,
            "observed_attempts": alert.observed_attempts,
            "all_costs_known": alert.all_costs_known,
            "policy_revision": policy.revision if policy else None,
            "policy_enabled": policy.enabled if policy else False,
        }

    app.include_router(router)
