"""Opt-in FM Command alert-policy writes; never tenant/self-service writes."""
from __future__ import annotations

import hmac
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from core.ai_command_authority import (
    CommandAuthorityDenied,
    CommandTrustPolicy,
    verify_command_platform_admin,
)
from core.ai_control_plane import ControlPlaneError
from core.ai_finops_alert_outbox import PersistentFinOpsAlertOutbox
from core.ai_finops_policy_store import PersistentFinOpsAlertPolicies
from core.ai_provider_billing_export import ProviderExportPolicy, ProviderExportRecord
from core.ai_provider_export_feed import configured_feed, fetch_observations
from core.ai_provider_export_store import PersistentProviderExportStore

_NONNEGATIVE_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?$")


class AlertPolicyUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tenant_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    unit_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    expected_revision: int = Field(ge=0)
    enabled: bool
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    maximum_known_cost: str = Field(min_length=1, max_length=80)


class AlertScanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tenant_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    unit_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    limit: int = Field(default=50, ge=1, le=100)
    after_request_id: str | None = Field(default=None, min_length=1, max_length=128)


class AlertReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tenant_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    unit_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    event_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProviderExportImportPayload(BaseModel):
    """Import observational usage after FM admin step-up; no provider invoices."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tenant_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    unit_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    request_id: str = Field(min_length=1, max_length=128)
    attempt_id: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=200)
    adapter: str = Field(pattern=r"^(openai_compatible|gemini)$")
    account_ref: str = Field(min_length=1, max_length=128)
    source_ref: str = Field(min_length=1, max_length=128)
    observed_at: datetime
    usage: dict[str, int | None] = Field(max_length=12)
    cost_usd: str | None = Field(default=None, max_length=80)


class ProviderExportSyncPayload(BaseModel):
    """Operator-triggered FM-managed source. No URL or secret in request."""

    model_config = ConfigDict(extra="forbid", strict=True)
    tenant_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    unit_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    provider: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    account_ref: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    page: int = Field(default=0, ge=0, le=20000, strict=True)
    limit: int = Field(default=25, ge=1, le=50, strict=True)


class ProviderExportBatchPayload(BaseModel):
    """Bounded FM-admin import. Each record names its physical Core attempt."""

    model_config = ConfigDict(extra="forbid", strict=True)
    records: list[ProviderExportImportPayload] = Field(min_length=1, max_length=50)


def finops_alert_policy_router(
    *, trust: CommandTrustPolicy, transport_key: str,
) -> APIRouter:
    if len(transport_key.encode()) < 32:
        raise ValueError("core_finops.alert_transport_invalid")
    router = APIRouter(prefix="/internal/v1/command", tags=["command-finops"])

    def require_fm_admin(
        authorization: str | None, key: str | None,
    ):
        if (
            not key or not hmac.compare_digest(transport_key, key)
            or not authorization or not authorization.startswith("Bearer ")
        ):
            raise HTTPException(status_code=401, detail="core_finops.alert_denied")
        try:
            return verify_command_platform_admin(
                authorization.removeprefix("Bearer "), trust,
            )
        except CommandAuthorityDenied as exc:
            raise HTTPException(
                status_code=403, detail="core_finops.alert_denied",
            ) from exc

    @router.post("/ai/finops/alert-scan")
    def scan_alert_queue(
        payload: AlertScanPayload,
        request: Request,
        authorization: str | None = Header(default=None),
        x_fm_recovery_service_key: str | None = Header(
            default=None, alias="X-FM-Recovery-Service-Key",
        ),
    ) -> dict[str, object]:
        # S2S credential + FM human platform-admin JWT. Scheduler remains OFF.
        require_fm_admin(authorization, x_fm_recovery_service_key)
        engine = getattr(request.app.state, "control_plane_engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="core_finops.alert_unavailable")
        try:
            result = PersistentFinOpsAlertOutbox(
                sessionmaker(engine, expire_on_commit=False),
            ).scan(
                tenant_id=payload.tenant_id, unit_id=payload.unit_id,
                start_date=date.fromisoformat(payload.start_date),
                end_date=date.fromisoformat(payload.end_date),
                limit=payload.limit, after_request_id=payload.after_request_id,
            )
        except (ControlPlaneError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="core_finops.alert_scan_invalid",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.alert_unavailable",
            ) from exc
        return {
            "created": result.created, "scanned": result.scanned,
            "next_cursor": result.next_cursor,
            "provider_invoice_verified": False,
            "automated_dispatch_enabled": False,
        }

    @router.post("/ai/finops/alert-review", status_code=204)
    def review_alert(
        payload: AlertReviewPayload,
        request: Request,
        authorization: str | None = Header(default=None),
        x_fm_recovery_service_key: str | None = Header(
            default=None, alias="X-FM-Recovery-Service-Key",
        ),
    ) -> None:
        principal = require_fm_admin(authorization, x_fm_recovery_service_key)
        engine = getattr(request.app.state, "control_plane_engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="core_finops.alert_unavailable")
        try:
            PersistentFinOpsAlertOutbox(
                sessionmaker(engine, expire_on_commit=False),
            ).mark_reviewed(
                event_id=payload.event_id, tenant_id=payload.tenant_id,
                unit_id=payload.unit_id, principal=principal,
            )
        except ControlPlaneError as exc:
            raise HTTPException(
                status_code=409, detail="core_finops.alert_review_conflict",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.alert_unavailable",
            ) from exc

    @router.post("/ai/finops/alert-policy", status_code=204)
    def update(
        payload: AlertPolicyUpdatePayload,
        request: Request,
        authorization: str | None = Header(default=None),
        x_fm_recovery_service_key: str | None = Header(
            default=None, alias="X-FM-Recovery-Service-Key",
        ),
    ) -> None:
        principal = require_fm_admin(
            authorization, x_fm_recovery_service_key,
        )
        if not _NONNEGATIVE_DECIMAL.fullmatch(payload.maximum_known_cost):
            raise HTTPException(status_code=422, detail="core_finops.alert_cost_invalid")
        try:
            amount = Decimal(payload.maximum_known_cost)
        except InvalidOperation as exc:
            raise HTTPException(status_code=422, detail="core_finops.alert_cost_invalid") from exc
        if not amount.is_finite() or not Decimal(0) < amount <= Decimal(1000000000):
            raise HTTPException(status_code=422, detail="core_finops.alert_cost_invalid")
        engine = getattr(request.app.state, "control_plane_engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="core_finops.alert_unavailable")
        try:
            PersistentFinOpsAlertPolicies(
                sessionmaker(engine, expire_on_commit=False),
            ).update(
                tenant_id=payload.tenant_id, unit_id=payload.unit_id,
                expected_revision=payload.expected_revision,
                enabled=payload.enabled, currency=payload.currency,
                maximum_known_cost=amount, principal=principal,
            )
        except (ControlPlaneError, InvalidOperation) as exc:
            raise HTTPException(status_code=409, detail="core_finops.alert_conflict") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="core_finops.alert_unavailable") from exc

    @router.post("/ai/finops/provider-export")
    def import_provider_export(
        payload: ProviderExportImportPayload,
        request: Request,
        authorization: str | None = Header(default=None),
        x_fm_recovery_service_key: str | None = Header(
            default=None, alias="X-FM-Recovery-Service-Key",
        ),
    ) -> dict[str, object]:
        """FM-controlled import; traceable, scoped and never billable itself."""
        principal = require_fm_admin(authorization, x_fm_recovery_service_key)
        engine = getattr(request.app.state, "control_plane_engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="core_finops.export_unavailable")
        try:
            policy = ProviderExportPolicy(
                provider=payload.provider, adapter=payload.adapter,
                account_ref=payload.account_ref,
                max_age_seconds=31 * 86400,
            )
            record = ProviderExportRecord(
                provider=payload.provider, model=payload.model,
                tenant_id=payload.tenant_id, unit_id=payload.unit_id,
                request_id=payload.request_id, attempt_id=payload.attempt_id,
                account_ref=payload.account_ref, source_ref=payload.source_ref,
                observed_at=payload.observed_at, usage=payload.usage,
                cost_usd=payload.cost_usd,
            )
            result = PersistentProviderExportStore(
                sessionmaker(engine, expire_on_commit=False),
            ).import_snapshot(
                policy=policy, record=record, principal=principal,
            )
        except ControlPlaneError as exc:
            raise HTTPException(
                status_code=409, detail="core_finops.export_rejected",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503, detail="core_finops.export_unavailable",
            ) from exc
        return {
            "status": result, "tenant_id": payload.tenant_id,
            "unit_id": payload.unit_id, "request_id": payload.request_id,
            "attempt_id": payload.attempt_id,
            "provider_invoice_verified": False,
            "quota_recovery_authorized": False,
        }

    @router.post("/ai/finops/provider-export/sync")
    def sync_configured_provider_export(
        payload: ProviderExportSyncPayload,
        request: Request,
        authorization: str | None = Header(default=None),
        x_fm_recovery_service_key: str | None = Header(
            default=None, alias="X-FM-Recovery-Service-Key",
        ),
    ) -> dict[str, object]:
        """Fetch configured source -> validate physical attempts -> atomic import.

        Server owns the feed URL/credential. Human FM authority authorizes
        the import; observational usage is never payment/settlement proof.
        """
        principal = require_fm_admin(authorization, x_fm_recovery_service_key)
        engine = getattr(request.app.state, "control_plane_engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="core_finops.export_unavailable")
        try:
            config = configured_feed(payload.provider, payload.account_ref)
            store = PersistentProviderExportStore(
                sessionmaker(engine, expire_on_commit=False),
            )
            coverage = store.coverage(
                tenant_id=payload.tenant_id, unit_id=payload.unit_id,
                start_date=date.fromisoformat(payload.start_date),
                end_date=date.fromisoformat(payload.end_date),
                page=payload.page, limit=payload.limit,
                # Page over all attempts: importing page 0 must not shift page 1.
                # Filtering the mutable "missing" set with OFFSET skips records.
                only_missing=False, provider=payload.provider,
            )
            attempts = [{
                "request_id": row["request_id"],
                "attempt_id": row["attempt_id"],
                "model": row["model"],
            } for row in coverage["items"]
              if row["export_status"] == "missing_provider_export"]
            if not attempts:
                return {
                    "created": 0, "already_recorded": 0,
                    "unreported": 0, "scanned": 0,
                    "next_page": coverage["next_page"],
                    "provider_invoice_verified": False,
                    "quota_recovery_authorized": False,
                }
            policy, records = fetch_observations(
                config=config, tenant_id=payload.tenant_id,
                unit_id=payload.unit_id, attempts=attempts,
            )
            outcome = (
                store.import_batch(policy=policy, records=records, principal=principal)
                if records else {"created": 0, "already_recorded": 0}
            )
        except (ControlPlaneError, ValueError) as exc:
            raise HTTPException(status_code=409, detail="core_finops.feed_sync_rejected") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="core_finops.export_unavailable") from exc
        return {
            **outcome, "scanned": len(attempts),
            "unreported": len(attempts) - len(records),
            "next_page": coverage["next_page"],
            "provider_invoice_verified": False,
            "quota_recovery_authorized": False,
        }

    @router.post("/ai/finops/provider-export/batch")
    def import_provider_export_batch(
        payload: ProviderExportBatchPayload,
        request: Request,
        authorization: str | None = Header(default=None),
        x_fm_recovery_service_key: str | None = Header(
            default=None, alias="X-FM-Recovery-Service-Key",
        ),
    ) -> dict[str, object]:
        """No machine impersonation: batch needs genuine FM admin JWT step-up."""
        principal = require_fm_admin(authorization, x_fm_recovery_service_key)
        engine = getattr(request.app.state, "control_plane_engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="core_finops.export_unavailable")
        first = payload.records[0]
        if any(
            (part.tenant_id, part.unit_id, part.provider, part.account_ref, part.adapter)
            != (first.tenant_id, first.unit_id, first.provider, first.account_ref,
                first.adapter)
            for part in payload.records
        ):
            raise HTTPException(status_code=409, detail="core_finops.export_batch_scope_invalid")
        try:
            policy = ProviderExportPolicy(
                provider=first.provider, adapter=first.adapter,
                account_ref=first.account_ref, max_age_seconds=31 * 86400,
            )
            records = tuple(ProviderExportRecord(
                provider=part.provider, model=part.model,
                tenant_id=part.tenant_id, unit_id=part.unit_id,
                request_id=part.request_id, attempt_id=part.attempt_id,
                account_ref=part.account_ref, source_ref=part.source_ref,
                observed_at=part.observed_at, usage=part.usage,
                cost_usd=part.cost_usd,
            ) for part in payload.records)
            outcome = PersistentProviderExportStore(
                sessionmaker(engine, expire_on_commit=False),
            ).import_batch(policy=policy, records=records, principal=principal)
        except ControlPlaneError as exc:
            raise HTTPException(status_code=409, detail="core_finops.export_batch_rejected") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="core_finops.export_unavailable") from exc
        return {
            **outcome, "tenant_id": first.tenant_id, "unit_id": first.unit_id,
            "provider": first.provider, "provider_invoice_verified": False,
            "quota_recovery_authorized": False,
        }

    return router
