"""F3: deterministic read-only reconciliation across provider retries and fallback.

Each supplied source statement is independently verified before matching to a
single immutable Core physical attempt. The result is an INVESTIGATION view,
not a provider invoice, financial settlement, or permission to release quota.
Unknown costs, failed attempts and partial evidence remain explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.ai_control_plane import ControlPlaneError
from core.ai_provider_source_verifier import ProviderSigningPolicy
from core.ai_provider_usage_match import MatchedProviderStatement, match_signed_provider_attempt
from core.ai_usage_ledger import AIUsageRecord, _observed_cost


@dataclass(frozen=True, kw_only=True)
class SignedAttemptEvidence:
    payload: bytes
    signature: bytes
    policy: ProviderSigningPolicy


@dataclass(frozen=True, kw_only=True)
class ProviderRequestReconciliation:
    tenant_id: str
    unit_id: str
    request_id: str
    attempts_observed: int
    statements_matched: int
    unmatched_attempts: int
    unknown_usage_attempts: int
    internal_cost_unknown_attempts: int
    statement_cost_unknown_attempts: int
    cost_disagreement_attempts: int
    internal_known_cost_usd_subtotal: Decimal
    statement_known_cost_usd_subtotal: Decimal
    matches: tuple[MatchedProviderStatement, ...]
    needs_attention: bool
    all_attempts_matched: bool
    invoice_verified: bool = False
    quota_recovery_authorized: bool = False


def reconcile_signed_provider_request(
    *, sessions: sessionmaker[Session],
    statements: tuple[SignedAttemptEvidence, ...],
    tenant_id: str, unit_id: str, request_id: str,
    at: datetime | None = None,
) -> ProviderRequestReconciliation:
    """Compare multiple independently signed sources to one Core request.

    Each statement must uniquely resolve an immutable success event. A failed
    route, missing statement, uncertain cost or discrepancy remains visible.
    Does not write the ledger, move quota, assert invoice verification or use
    unverified vendor telemetry as independent financial proof.
    """
    if type(statements) is not tuple or not 1 <= len(statements) <= 100:
        raise ControlPlaneError("core_finops.reconciliation_invalid_batch")
    if any(not isinstance(item, SignedAttemptEvidence) or
           type(item.payload) is not bytes or
           type(item.signature) is not bytes or
           not isinstance(item.policy, ProviderSigningPolicy) for item in statements):
        raise ControlPlaneError("core_finops.reconciliation_invalid_source")

    matches: list[MatchedProviderStatement] = []
    used: set[str] = set()
    for statement in statements:
        match = match_signed_provider_attempt(
            sessions=sessions, source_payload=statement.payload,
            source_signature=statement.signature, source_policy=statement.policy,
            tenant_id=tenant_id, unit_id=unit_id, request_id=request_id, at=at,
        )
        if match.attempt_id in used:
            raise ControlPlaneError("core_finops.reconciliation_duplicate_attempt")
        used.add(match.attempt_id)
        matches.append(match)

    with sessions() as db:
        events = db.scalars(select(AIUsageRecord).where(
            AIUsageRecord.tenant_id == tenant_id,
            AIUsageRecord.unit_id == unit_id,
            AIUsageRecord.request_id == request_id,
        ).limit(101)).all()
    if not events or len(events) > 100:
        raise ControlPlaneError("core_finops.reconciliation_unbounded_attempts")
    present_ids = {event.event_id for event in events}
    if len(present_ids) != len(events) or not used.issubset(present_ids):
        raise ControlPlaneError("core_finops.reconciliation_changed_ledger")
    unmatched = len(events) - len(used)
    unknown_usage = sum(
        event.input_tokens is None or event.output_tokens is None for event in events
    )
    unknown_cost = 0
    internal_subtotal = Decimal(0)
    for event in events:
        cost = _observed_cost(event.cost_decimal)
        if cost is None:
            unknown_cost += 1
        else:
            if event.currency != "USD":
                raise ControlPlaneError("core_finops.reconciliation_currency_mismatch")
            internal_subtotal += cost

    statement_unknown = sum(
        match.provider_statement_cost_usd is None for match in matches
    )
    statement_subtotal = sum(
        (match.provider_statement_cost_usd
         for match in matches if match.provider_statement_cost_usd is not None),
        Decimal(0),
    )
    discrepancy = sum(
        match.provider_statement_cost_usd is not None
        and match.internally_estimated_cost_usd is not None
        and match.provider_statement_cost_usd != match.internally_estimated_cost_usd
        for match in matches
    )
    incomplete = bool(unmatched or unknown_usage or unknown_cost or
                      statement_unknown or discrepancy)
    return ProviderRequestReconciliation(
        tenant_id=tenant_id, unit_id=unit_id, request_id=request_id,
        attempts_observed=len(events), statements_matched=len(matches),
        unmatched_attempts=unmatched, unknown_usage_attempts=unknown_usage,
        internal_cost_unknown_attempts=unknown_cost,
        statement_cost_unknown_attempts=statement_unknown,
        cost_disagreement_attempts=discrepancy,
        internal_known_cost_usd_subtotal=internal_subtotal,
        statement_known_cost_usd_subtotal=statement_subtotal,
        matches=tuple(matches), needs_attention=incomplete,
        all_attempts_matched=not bool(unmatched),
    )
