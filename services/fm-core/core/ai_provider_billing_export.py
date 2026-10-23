"""F3 provider-specific *observational* billing export readback, no settlements.

Provider APIs commonly return metering without a signed financial invoice.
An approved service adapter owns transport/authentication and supplies a
scoped export record. This module cannot upgrade that transport response into
independent cryptographic proof, invoice verification or quota recovery.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.ai_control_plane import ControlPlaneError
from core.ai_usage_ledger import AIUsageRecord, _observed_cost


@dataclass(frozen=True, kw_only=True)
class ProviderExportPolicy:
    provider: str
    adapter: str
    account_ref: str
    max_age_seconds: int = 86400

    def __post_init__(self) -> None:
        if (
            type(self.provider) is not str or not 1 <= len(self.provider) <= 128
            or self.adapter not in {"openai_compatible", "gemini"}
            or type(self.account_ref) is not str or not 1 <= len(self.account_ref) <= 128
            or type(self.max_age_seconds) is not int
            or not 60 <= self.max_age_seconds <= 31 * 86400
        ):
            raise ControlPlaneError("core_finops.export_policy_invalid")


@dataclass(frozen=True, kw_only=True)
class ProviderExportRecord:
    provider: str
    account_ref: str
    tenant_id: str
    unit_id: str
    request_id: str
    attempt_id: str
    model: str
    source_ref: str
    observed_at: datetime
    usage: Mapping[str, object]
    cost_usd: str | None


class ProviderExportReadPort(Protocol):
    """Pluggable configured authenticated fetcher; no browser-supplied data."""

    def read_attempt(
        self, *, policy: ProviderExportPolicy, tenant_id: str,
        unit_id: str, request_id: str, attempt_id: str,
    ) -> ProviderExportRecord | None: ...


@dataclass(frozen=True, kw_only=True)
class ProviderExportComparison:
    attempt_id: str
    request_id: str
    provider: str
    source_ref: str | None
    input_tokens_reported: int | None
    output_tokens_reported: int | None
    report_cost_usd: Decimal | None
    internal_cost_usd: Decimal | None
    usage_matches: bool | None
    cost_matches: bool | None
    needs_attention: bool
    status: str
    # These stay false even for perfect numeric matches.
    provider_invoice_verified: bool = False
    provider_signature_verified: bool = False
    quota_recovery_authorized: bool = False


def _strict_meter(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 2_000_000_000:
        raise ControlPlaneError("core_finops.export_meter_invalid")
    return value


def _usage_counts(adapter: str, usage: Mapping[str, object]) -> tuple[int | None, int | None]:
    if adapter == "openai_compatible":
        return _strict_meter(usage.get("prompt_tokens")), _strict_meter(
            usage.get("completion_tokens")
        )
    if adapter == "gemini":
        return _strict_meter(usage.get("promptTokenCount")), _strict_meter(
            usage.get("candidatesTokenCount")
        )
    raise ControlPlaneError("core_finops.export_adapter_invalid")


def readback_provider_export_attempt(
    *, sessions: sessionmaker[Session], port: ProviderExportReadPort,
    policy: ProviderExportPolicy, tenant_id: str, unit_id: str,
    request_id: str, attempt_id: str, now: datetime | None = None,
) -> ProviderExportComparison:
    """Read-only matching against exactly one ledger physical attempt.

    A transport snapshot can contradict, corroborate or be missing from
    our ledger; none of those outcomes certify vendor invoices.
    """
    for value in (tenant_id, unit_id, request_id, attempt_id):
        if type(value) is not str or not 1 <= len(value) <= 128:
            raise ControlPlaneError("core_finops.export_scope_invalid")
    current = now or datetime.now(UTC)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ControlPlaneError("core_finops.export_time_invalid")
    with sessions() as db:
        rows = db.scalars(select(AIUsageRecord).where(
            AIUsageRecord.tenant_id == tenant_id,
            AIUsageRecord.unit_id == unit_id,
            AIUsageRecord.request_id == request_id,
            AIUsageRecord.attempt_id == attempt_id,
        ).limit(2)).all()
    if len(rows) != 1:
        raise ControlPlaneError("core_finops.export_attempt_not_unique")
    event = rows[0]
    if event.provider != policy.provider:
        raise ControlPlaneError("core_finops.export_provider_mismatch")
    internal_cost = _observed_cost(event.cost_decimal)
    if internal_cost is not None and event.currency != "USD":
        raise ControlPlaneError("core_finops.export_currency_mismatch")
    export = port.read_attempt(
        policy=policy, tenant_id=tenant_id, unit_id=unit_id,
        request_id=request_id, attempt_id=attempt_id,
    )
    if export is None:
        return ProviderExportComparison(
            attempt_id=attempt_id, request_id=request_id, provider=policy.provider,
            source_ref=None, input_tokens_reported=None, output_tokens_reported=None,
            report_cost_usd=None, internal_cost_usd=internal_cost,
            usage_matches=None, cost_matches=None,
            needs_attention=True, status="missing_provider_export",
        )
    if not isinstance(export, ProviderExportRecord) or (
        export.provider, export.account_ref, export.tenant_id,
        export.unit_id, export.request_id, export.attempt_id, export.model,
    ) != (
        policy.provider, policy.account_ref, tenant_id, unit_id,
        request_id, attempt_id, event.model,
    ):
        raise ControlPlaneError("core_finops.export_scope_mismatch")
    if (
        type(export.source_ref) is not str or not 1 <= len(export.source_ref) <= 128
        or not isinstance(export.observed_at, datetime)
        or export.observed_at.tzinfo is None
        or not isinstance(export.usage, Mapping)
        or not isinstance(export.cost_usd, (str, type(None)))
    ):
        raise ControlPlaneError("core_finops.export_shape_invalid")
    age = (current - export.observed_at).total_seconds()
    if age < -15 or age > policy.max_age_seconds:
        raise ControlPlaneError("core_finops.export_stale_or_future")
    inp, out = _usage_counts(policy.adapter, export.usage)
    if export.cost_usd is not None:
        if re.fullmatch(r"[0-9]{1,16}(?:\.[0-9]{1,18})?", export.cost_usd) is None:
            raise ControlPlaneError("core_finops.export_cost_invalid")
        reported_cost = _observed_cost(export.cost_usd)
    else:
        reported_cost = None
    usage_matches = (
        inp == event.input_tokens and out == event.output_tokens
        if inp is not None and out is not None
        and event.input_tokens is not None and event.output_tokens is not None
        else None
    )
    cost_matches = (
        reported_cost == internal_cost
        if reported_cost is not None and internal_cost is not None else None
    )
    needs_attention = (
        usage_matches is not True or cost_matches is not True
        or event.outcome != "success"
    )
    return ProviderExportComparison(
        attempt_id=attempt_id, request_id=request_id, provider=policy.provider,
        source_ref=export.source_ref,
        input_tokens_reported=inp, output_tokens_reported=out,
        report_cost_usd=reported_cost, internal_cost_usd=internal_cost,
        usage_matches=usage_matches, cost_matches=cost_matches,
        needs_attention=needs_attention,
        status="needs_attention" if needs_attention else "observational_match",
    )
