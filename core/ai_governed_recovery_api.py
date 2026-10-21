"""Optional internal Command recovery route.

Not mounted in the production app until a trusted provider evidence verifier
and Command public trust configuration are supplied. This makes an unverified
provider proof a hard construction gate, not a path to free quota.
"""
from __future__ import annotations

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.ai_command_authority import (
    CommandAuthorityDenied,
    CommandTrustPolicy,
)
from core.ai_governed_recovery import (
    GovernedRecoveryCommand,
    ProviderEvidenceVerifier,
    RecoveryQuotaLedger,
    execute_governed_recovery,
)
from core.ai_quota_store import QuotaDenied


class GovernedRecoveryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    tenant_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    unit_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    evidence_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    requests_revision: int = Field(ge=1)
    tokens_revision: int = Field(ge=1)


def governed_recovery_router(
    *, trust: CommandTrustPolicy,
    evidence: ProviderEvidenceVerifier, ledger: RecoveryQuotaLedger,
    transport_key: str,
) -> APIRouter:
    # Service identity is independent from Command's human RS256 step-up.
    if not isinstance(transport_key, str) or len(transport_key.encode()) < 32:
        raise ValueError("core_recovery_transport_key_invalid")
    router = APIRouter(prefix="/internal/v1/command", tags=["command-recovery"])

    @router.post("/ai/usage/reconcile", status_code=204)
    def reconcile(
        payload: GovernedRecoveryPayload,
        authorization: str | None = Header(default=None),
        x_fm_recovery_service_key: str | None = Header(
            default=None, alias="X-FM-Recovery-Service-Key",
        ),
    ) -> None:
        if (
            not x_fm_recovery_service_key
            or not hmac.compare_digest(transport_key, x_fm_recovery_service_key)
        ):
            raise HTTPException(status_code=401, detail="command_recovery_denied")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="command_recovery_denied")
        token = authorization.removeprefix("Bearer ")
        try:
            execute_governed_recovery(
                command=GovernedRecoveryCommand(**payload.model_dump()),
                bearer_token=token, trust=trust, evidence=evidence,
                ledger=ledger, at=datetime.now(UTC),
            )
        except CommandAuthorityDenied as exc:
            raise HTTPException(
                status_code=403, detail="command_recovery_denied",
            ) from exc
        except QuotaDenied as exc:
            raise HTTPException(
                status_code=409, detail="command_recovery_conflict",
            ) from exc

    return router
