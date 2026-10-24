"""Persist FM-authorized *observational* provider exports and compare with Core usage.

Import is a human-approved Command operation under the existing signed S2S
boundary. Matching an export never certifies an invoice, settles money, or
releases tenant quota. Conflicting re-imports cannot rewrite history.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import DateTime, Index, String, UniqueConstraint, and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from core.ai_admin_audit import stage_admin_mutation_audit
from core.ai_command_authority import VerifiedCommandAdmin
from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_provider_billing_export import (
    ProviderExportComparison,
    ProviderExportPolicy,
    ProviderExportRecord,
    readback_provider_export_attempt,
)
from core.ai_usage_ledger import AIUsageRecord, _observed_cost


class AIProviderExportRecord(ControlPlaneBase):
    __tablename__ = "core_ai_provider_export_snapshots"

    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter: Mapped[str] = mapped_column(String(32), nullable=False)
    account_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usage_json: Mapped[str] = mapped_column(String(2048), nullable=False)
    cost_usd: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "unit_id", "request_id", "attempt_id",
            name="uq_core_provider_export_physical_attempt",
        ),
        UniqueConstraint(
            "provider", "account_ref", "source_ref",
            name="uq_core_provider_export_source_provenance",
        ),
        Index("ix_core_provider_export_scope", "tenant_id", "unit_id", "request_id"),
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _snapshot(policy: ProviderExportPolicy, record: ProviderExportRecord) -> tuple[str, str]:
    if not isinstance(record, ProviderExportRecord) or not isinstance(policy, ProviderExportPolicy):
        raise ControlPlaneError("core_finops.export_invalid")
    if not all(isinstance(value, str) and 1 <= len(value) <= 128 for value in (
        record.tenant_id, record.unit_id, record.request_id, record.attempt_id,
        record.provider, record.account_ref, record.source_ref,
    )):
        raise ControlPlaneError("core_finops.export_scope_invalid")
    if not isinstance(record.observed_at, datetime) or record.observed_at.tzinfo is None:
        raise ControlPlaneError("core_finops.export_time_invalid")
    required = ({"prompt_tokens", "completion_tokens"} if policy.adapter == "openai_compatible"
                else {"promptTokenCount", "candidatesTokenCount"})
    if (
        record.provider != policy.provider or record.account_ref != policy.account_ref
        or not isinstance(record.model, str) or not 1 <= len(record.model) <= 200
        or not isinstance(record.usage, dict) or set(record.usage) != required
    ):
        raise ControlPlaneError("core_finops.export_policy_mismatch")
    try:
        usage_json = json.dumps(
            record.usage, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ControlPlaneError("core_finops.export_usage_invalid") from exc
    if len(usage_json) > 2048:
        raise ControlPlaneError("core_finops.export_usage_too_large")
    canonical = json.dumps({
        "schema": "fm.core.provider-export.v1",
        "tenant_id": record.tenant_id, "unit_id": record.unit_id,
        "request_id": record.request_id, "attempt_id": record.attempt_id,
        "provider": record.provider, "model": record.model,
        "adapter": policy.adapter, "account_ref": record.account_ref,
        "source_ref": record.source_ref,
        "observed_at": _aware(record.observed_at).isoformat(),
        "usage": json.loads(usage_json), "cost_usd": record.cost_usd,
    }, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest(), usage_json


def _domain(row: AIProviderExportRecord) -> ProviderExportRecord:
    return ProviderExportRecord(
        tenant_id=row.tenant_id, unit_id=row.unit_id,
        request_id=row.request_id, attempt_id=row.attempt_id,
        provider=row.provider, model=row.model,
        account_ref=row.account_ref, source_ref=row.source_ref,
        observed_at=_aware(row.observed_at),
        usage=json.loads(row.usage_json), cost_usd=row.cost_usd,
    )


class _SingleSource:
    def __init__(self, record: ProviderExportRecord) -> None:
        self._record = record

    def read_attempt(
        self, *, policy: ProviderExportPolicy, tenant_id: str,
        unit_id: str, request_id: str, attempt_id: str,
    ) -> ProviderExportRecord:
        return self._record


class PersistentProviderExportStore:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def import_snapshot(
        self, *, policy: ProviderExportPolicy, record: ProviderExportRecord,
        principal: VerifiedCommandAdmin, now: datetime | None = None,
    ) -> Literal["created", "already_recorded"]:
        """Import an immutable snapshot once; signer/jti consumed only for writes."""
        at = now or datetime.now(UTC)
        digest, usage_json = _snapshot(policy, record)
        # Only compare against a real Core physical attempt, not client metadata.
        readback_provider_export_attempt(
            sessions=self._sessions, port=_SingleSource(record),
            policy=policy, tenant_id=record.tenant_id, unit_id=record.unit_id,
            request_id=record.request_id, attempt_id=record.attempt_id, now=at,
        )
        with self._sessions.begin() as db:
            prior = db.scalar(select(AIProviderExportRecord).where(
                AIProviderExportRecord.tenant_id == record.tenant_id,
                AIProviderExportRecord.unit_id == record.unit_id,
                AIProviderExportRecord.request_id == record.request_id,
                AIProviderExportRecord.attempt_id == record.attempt_id,
            ))
            if prior is not None:
                if prior.digest != digest:
                    raise ControlPlaneError("core_finops.export_conflicting_snapshot")
                return "already_recorded"
            # Caller already passed both Command operator JWT and independent
            # FM service transport secret in the HTTP route.
            stage_admin_mutation_audit(
                db, principal=principal,
                action="finops.provider_export.import",
                resource_id=digest,
                canonical_request=digest.encode("ascii"),
            )
            db.add(AIProviderExportRecord(
                digest=digest, tenant_id=record.tenant_id, unit_id=record.unit_id,
                request_id=record.request_id, attempt_id=record.attempt_id,
                provider=record.provider, model=record.model, adapter=policy.adapter,
                account_ref=record.account_ref, source_ref=record.source_ref,
                observed_at=_aware(record.observed_at), imported_at=_aware(at),
                usage_json=usage_json, cost_usd=record.cost_usd,
            ))
            try:
                db.flush()
            except IntegrityError as exc:
                raise ControlPlaneError("core_finops.export_duplicate_or_conflicting") from exc
        return "created"

    def import_batch(
        self, *, policy: ProviderExportPolicy,
        records: tuple[ProviderExportRecord, ...],
        principal: VerifiedCommandAdmin,
        now: datetime | None = None,
    ) -> dict[str, int]:
        """One FM human authorization, one audit and one atomic transaction.

        Mixed scope/provider batches, duplicate identities and conflicting
        source provenance fail closed. Replay only reports already_imported.
        No invoice or quota state is modified.
        """
        if (
            type(records) is not tuple or not 1 <= len(records) <= 50
            or not isinstance(policy, ProviderExportPolicy)
        ):
            raise ControlPlaneError("core_finops.export_batch_invalid")
        at = now or datetime.now(UTC)
        scope = (records[0].tenant_id, records[0].unit_id)
        unique_attempts: set[tuple[str, str]] = set()
        unique_sources: set[str] = set()
        staged: list[tuple[ProviderExportRecord, str, str]] = []
        for record in records:
            if (record.tenant_id, record.unit_id) != scope:
                raise ControlPlaneError("core_finops.export_batch_scope_mismatch")
            digest, usage_json = _snapshot(policy, record)
            physical_key = (record.request_id, record.attempt_id)
            if physical_key in unique_attempts or record.source_ref in unique_sources:
                raise ControlPlaneError("core_finops.export_batch_duplicate")
            unique_attempts.add(physical_key)
            unique_sources.add(record.source_ref)
            readback_provider_export_attempt(
                sessions=self._sessions, port=_SingleSource(record),
                policy=policy, tenant_id=record.tenant_id, unit_id=record.unit_id,
                request_id=record.request_id, attempt_id=record.attempt_id,
                now=at,
            )
            staged.append((record, digest, usage_json))
        created = 0
        already = 0
        with self._sessions.begin() as db:
            for record, digest, usage_json in staged:
                prior = db.scalar(select(AIProviderExportRecord).where(
                    AIProviderExportRecord.tenant_id == record.tenant_id,
                    AIProviderExportRecord.unit_id == record.unit_id,
                    AIProviderExportRecord.request_id == record.request_id,
                    AIProviderExportRecord.attempt_id == record.attempt_id,
                ))
                if prior is not None:
                    if prior.digest != digest:
                        raise ControlPlaneError("core_finops.export_conflicting_snapshot")
                    already += 1
                    continue
                db.add(AIProviderExportRecord(
                    digest=digest, tenant_id=record.tenant_id,
                    unit_id=record.unit_id, request_id=record.request_id,
                    attempt_id=record.attempt_id, provider=record.provider,
                    model=record.model, adapter=policy.adapter,
                    account_ref=record.account_ref, source_ref=record.source_ref,
                    observed_at=_aware(record.observed_at),
                    imported_at=_aware(at), usage_json=usage_json,
                    cost_usd=record.cost_usd,
                ))
                created += 1
            if created:
                batch_digest = hashlib.sha256(
                    ("fm.provider.batch.v1|" + "|".join(
                        digest for _, digest, _ in staged
                    )).encode("ascii")
                ).hexdigest()
                # One human step-up assertion authorizes this bounded batch.
                stage_admin_mutation_audit(
                    db, principal=principal,
                    action="finops.provider_export.import_batch",
                    resource_id=batch_digest,
                    canonical_request=batch_digest.encode("ascii"),
                )
                try:
                    db.flush()
                except IntegrityError as exc:
                    raise ControlPlaneError(
                        "core_finops.export_duplicate_or_conflicting"
                    ) from exc
        return {"created": created, "already_recorded": already}

    def coverage(
        self, *, tenant_id: str, unit_id: str,
        start_date: date, end_date: date,
        page: int = 0, limit: int = 50,
        only_missing: bool = False,
        provider: str | None = None,
    ) -> dict[str, object]:
        """Bounded per-attempt coverage; observations are not invoice evidence.

        Include failed and fallback attempts: dropping them could conceal a
        vendor charge. Missing exports remain unknown, not cost zero.
        """
        if any(
            type(v) is not str or not 1 <= len(v) <= 128
            for v in (tenant_id, unit_id)
        ) or (
            type(start_date) is not date or type(end_date) is not date
            or start_date > end_date or (end_date - start_date).days > 92
            or type(page) is not int or not 0 <= page <= 20_000
            or type(limit) is not int or not 1 <= limit <= 100
            or type(only_missing) is not bool
            or (provider is not None and (
                type(provider) is not str or not 1 <= len(provider) <= 128
            ))
        ):
            raise ControlPlaneError("core_finops.export_coverage_invalid")
        start_at = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        predicate = [
            AIUsageRecord.tenant_id == tenant_id,
            AIUsageRecord.unit_id == unit_id,
            AIUsageRecord.event_time >= start_at,
            AIUsageRecord.event_time < end_at,
            AIUsageRecord.attempt_id.is_not(None),
            AIUsageRecord.attempt_id != "",
        ]
        join = and_(
            AIProviderExportRecord.tenant_id == AIUsageRecord.tenant_id,
            AIProviderExportRecord.unit_id == AIUsageRecord.unit_id,
            AIProviderExportRecord.request_id == AIUsageRecord.request_id,
            AIProviderExportRecord.attempt_id == AIUsageRecord.attempt_id,
        )
        if only_missing:
            predicate.append(AIProviderExportRecord.digest.is_(None))
        if provider is not None:
            predicate.append(AIUsageRecord.provider == provider)
        with self._sessions() as db:
            rows = db.execute(
                select(AIUsageRecord, AIProviderExportRecord)
                .outerjoin(AIProviderExportRecord, join)
                .where(*predicate)
                .order_by(
                    AIUsageRecord.event_time, AIUsageRecord.event_id,
                ).offset(page * limit).limit(limit + 1)
            ).all()
        items = []
        for attempt, export in rows[:limit]:
            result = (
                self.compare(
                    tenant_id=tenant_id, unit_id=unit_id,
                    request_id=attempt.request_id,
                    attempt_id=attempt.attempt_id,
                ) if export is not None else None
            )
            items.append({
                "request_id": attempt.request_id,
                "attempt_id": attempt.attempt_id,
                "event_id": attempt.event_id,
                "provider": attempt.provider,
                "model": attempt.model,
                "outcome": attempt.outcome,
                "fallback": bool(attempt.fallback_used),
                "export_status": (
                    result.status if result else "missing_provider_export"
                ),
                "source_ref": result.source_ref if result else None,
                "usage_matches": result.usage_matches if result else None,
                "cost_matches": result.cost_matches if result else None,
                "needs_attention": result.needs_attention if result else True,
                "provider_invoice_verified": False,
                "quota_recovery_authorized": False,
            })
        return {
            "tenant_id": tenant_id,
            "unit_id": unit_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "items": items,
            "next_page": page + 1 if len(rows) > limit else None,
            "page_only": True,
            "provider_invoice_verified": False,
        }


    def reconcile_request(
        self, *, tenant_id: str, unit_id: str, request_id: str,
    ) -> dict[str, object]:
        """F3 diagnostic across *all* physical attempts and fallback providers.

        Observational exports never mean a verified provider invoice, money
        settlement or permission to release a tenant quota. A failed attempt
        can still be billed. No cost is invented for absent provider reports.
        """
        if any(
            type(part) is not str or not 1 <= len(part) <= 128
            for part in (tenant_id, unit_id, request_id)
        ):
            raise ControlPlaneError("core_finops.request_scope_invalid")
        with self._sessions() as db:
            attempts = db.scalars(
                select(AIUsageRecord).where(
                    AIUsageRecord.tenant_id == tenant_id,
                    AIUsageRecord.unit_id == unit_id,
                    AIUsageRecord.request_id == request_id,
                ).order_by(AIUsageRecord.event_time, AIUsageRecord.event_id)
                .limit(101)
            ).all()
        if not attempts:
            raise ControlPlaneError("core_finops.request_not_found")
        if len(attempts) > 100:
            raise ControlPlaneError("core_finops.request_unbounded_attempts")
        seen: set[str] = set()
        reports: dict[str, dict[str, object]] = {}
        observations: list[dict[str, object]] = []
        for attempt in attempts:
            attempt_id = attempt.attempt_id
            if not attempt_id or attempt_id in seen:
                # Ambiguous physical attempt IDs prevent reliable comparison.
                raise ControlPlaneError("core_finops.request_attempt_identity_invalid")
            seen.add(attempt_id)
            internal = _observed_cost(attempt.cost_decimal)
            if internal is not None and attempt.currency != "USD":
                raise ControlPlaneError("core_finops.request_currency_mismatch")
            compared = self.compare(
                tenant_id=tenant_id, unit_id=unit_id,
                request_id=request_id, attempt_id=attempt_id,
            )
            provider = attempt.provider
            summary = reports.setdefault(provider, {
                "provider": provider, "attempts": 0, "fallback_attempts": 0,
                "missing_exports": 0, "uncertain_attempts": 0,
                "cost_disagreements": 0, "internal_known_cost_usd": Decimal(0),
                "reported_known_cost_usd": Decimal(0),
                "internal_unknown_costs": 0, "reported_unknown_costs": 0,
            })
            summary["attempts"] += 1
            summary["fallback_attempts"] += int(bool(attempt.fallback_used))
            summary["missing_exports"] += int(compared is None)
            summary["internal_unknown_costs"] += int(internal is None)
            if internal is not None:
                summary["internal_known_cost_usd"] += internal
            reported = compared.report_cost_usd if compared else None
            summary["reported_unknown_costs"] += int(reported is None)
            if reported is not None:
                summary["reported_known_cost_usd"] += reported
            discrepancy = bool(compared and compared.cost_matches is False)
            summary["cost_disagreements"] += int(discrepancy)
            attention = compared is None or compared.needs_attention or (
                internal is None or reported is None
            )
            summary["uncertain_attempts"] += int(attention)
            observations.append({
                "attempt_id": attempt_id, "provider": provider,
                "model": attempt.model, "outcome": attempt.outcome,
                "fallback": bool(attempt.fallback_used),
                "source_ref": compared.source_ref if compared else None,
                "export_status": compared.status if compared else "missing_provider_export",
                "usage_matches": compared.usage_matches if compared else None,
                "cost_matches": compared.cost_matches if compared else None,
                "needs_attention": attention,
            })
        per_provider = []
        for provider in sorted(reports):
            summary = reports[provider]
            per_provider.append({
                **summary,
                "internal_known_cost_usd": str(summary["internal_known_cost_usd"]),
                "reported_known_cost_usd": str(summary["reported_known_cost_usd"]),
            })
        return {
            "tenant_id": tenant_id, "unit_id": unit_id, "request_id": request_id,
            "attempts_observed": len(attempts),
            "fallback_attempts": sum(int(bool(x.fallback_used)) for x in attempts),
            "per_provider": per_provider, "attempts": observations,
            "needs_attention": any(row["needs_attention"] for row in observations),
            "all_observational_matches": all(
                not row["needs_attention"] for row in observations
            ),
            "provider_invoice_verified": False,
            "quota_recovery_authorized": False,
            "real_provider_charges_certified": False,
        }

    def compare(
        self, *, tenant_id: str, unit_id: str, request_id: str,
        attempt_id: str, now: datetime | None = None,
    ) -> ProviderExportComparison | None:
        if any(
            type(part) is not str or not 1 <= len(part) <= 128
            for part in (tenant_id, unit_id, request_id, attempt_id)
        ):
            raise ControlPlaneError("core_finops.export_scope_invalid")
        with self._sessions() as db:
            row = db.scalar(select(AIProviderExportRecord).where(
                AIProviderExportRecord.tenant_id == tenant_id,
                AIProviderExportRecord.unit_id == unit_id,
                AIProviderExportRecord.request_id == request_id,
                AIProviderExportRecord.attempt_id == attempt_id,
            ))
            if row is None:
                return None
            policy = ProviderExportPolicy(
                provider=row.provider, account_ref=row.account_ref,
                adapter=row.adapter,
                # Snapshots are append-only, with an independently traceable
                # import time. Historical comparisons do not expire retroactively.
                max_age_seconds=31 * 86400,
            )
            record = _domain(row)
        return readback_provider_export_attempt(
            sessions=self._sessions, port=_SingleSource(record), policy=policy,
            tenant_id=tenant_id, unit_id=unit_id, request_id=request_id,
            attempt_id=attempt_id, now=now or _aware(row.imported_at),
        )
