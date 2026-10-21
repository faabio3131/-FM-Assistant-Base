"""Authenticated Command recovery orchestration; evidence must be independently verified.

No model, user-supplied hash, or mere provider record is proof. The verification
authority is supplied by a separate trusted component, never by the HTTP caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from core.ai_command_authority import (
    CommandTrustPolicy,
    VerifiedCommandAdmin,
    verify_command_platform_admin,
)
from core.ai_quota_store import QuotaDenied
from core.ai_verified_usage_receipt import VerifiedProviderUsageReceipt


class ProviderEvidenceVerifier(Protocol):
    def verify(
        self, *, evidence_id: str, request_id: str,
        tenant_id: str, unit_id: str,
    ) -> VerifiedProviderUsageReceipt:
        """Fetch independently authenticated provider receipt; no caller values."""


class RecoveryQuotaLedger(Protocol):
    """Minimal quota-reconciliation port; Core ledger remains authoritative."""

    def reconcile_verified_provider_receipt(
        self, *, receipt: VerifiedProviderUsageReceipt,
        request_policy_revision: int, tokens_policy_revision: int,
        principal: VerifiedCommandAdmin, at: datetime,
        request_scope: str = "__tenant__", tokens_scope: str = "__tenant__",
    ) -> None: ...


@dataclass(frozen=True, kw_only=True)
class GovernedRecoveryCommand:
    request_id: str
    tenant_id: str
    unit_id: str
    evidence_id: str
    requests_revision: int
    tokens_revision: int


def execute_governed_recovery(
    *, command: GovernedRecoveryCommand, bearer_token: str,
    trust: CommandTrustPolicy, evidence: ProviderEvidenceVerifier,
    ledger: RecoveryQuotaLedger, at: datetime,
) -> None:
    """Verify human Command token and evidence independently before settlement.

    The caller supplies only an opaque reference. Verified content is retrieved
    from a protected source; token and receipt are never persisted here.
    """
    import re

    if (
        not all(
            isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value)
            for value in (
                command.request_id, command.tenant_id,
                command.unit_id, command.evidence_id,
            )
        )
        or type(command.requests_revision) is not int
        or type(command.tokens_revision) is not int
        or command.requests_revision < 1 or command.tokens_revision < 1
    ):
        raise QuotaDenied("core_recovery_command_invalid")
    principal = verify_command_platform_admin(bearer_token, trust, now=at)
    receipt = evidence.verify(
        evidence_id=command.evidence_id,
        request_id=command.request_id,
        tenant_id=command.tenant_id,
        unit_id=command.unit_id,
    )
    if not isinstance(receipt, VerifiedProviderUsageReceipt):
        raise QuotaDenied("core_recovery_evidence_unverified")
    if (
        receipt.request_id != command.request_id
        or receipt.tenant_id != command.tenant_id
        or receipt.unit_id != command.unit_id
    ):
        raise QuotaDenied("core_recovery_evidence_scope_mismatch")
    ledger.reconcile_verified_provider_receipt(
        receipt=receipt, request_policy_revision=command.requests_revision,
        tokens_policy_revision=command.tokens_revision, principal=principal, at=at,
    )
