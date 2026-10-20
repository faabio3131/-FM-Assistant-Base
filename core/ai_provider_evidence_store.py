"""Immutable FM-verified provider evidence references for governed AI recovery.

A source gateway must verify a provider statement before signing this compact
attestation. The signature authenticates the FM gateway, NOT an intrinsic
signature of Gemini/OpenAI/etc. Production source-verifier certification stays
independent from software construction.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker, Session

from core.ai_control_plane import ControlPlaneBase
from core.ai_quota_store import QuotaDenied
from core.ai_verified_usage_receipt import VerifiedProviderUsageReceipt


class TrustedProviderEvidenceRecord(ControlPlaneBase):
    __tablename__ = "core_ai_provider_evidence"

    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    no_charge: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )


def _canonical(evidence_id: str, source_id: str, receipt: VerifiedProviderUsageReceipt) -> bytes:
    if (
        not isinstance(evidence_id, str)
        or not isinstance(source_id, str)
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", evidence_id) is None
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", source_id) is None
    ):
        raise QuotaDenied("core_evidence_reference_invalid")
    return json.dumps({
        "evidence_id": evidence_id, "source_id": source_id,
        "tenant_id": receipt.tenant_id, "unit_id": receipt.unit_id,
        "request_id": receipt.request_id, "provider": receipt.provider,
        "model": receipt.model, "input_tokens": receipt.input_tokens,
        "output_tokens": receipt.output_tokens,
        "cost_usd": str(receipt.provider_cost_usd)
        if receipt.provider_cost_usd is not None else None,
        "no_charge": receipt.no_charge,
        "evidence_digest": receipt.evidence_digest,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_verified_gateway_attestation(
    *, evidence_id: str, source_id: str,
    receipt: VerifiedProviderUsageReceipt, secret: bytes,
) -> str:
    """Gateway-only signer for test/source component; not callable by a tenant."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise QuotaDenied("core_evidence_gateway_key_invalid")
    return hmac.new(
        secret, b"FM_CORE_PROVIDER_EVIDENCE_V1\n" +
        _canonical(evidence_id, source_id, receipt), hashlib.sha256,
    ).hexdigest()


class TrustedProviderEvidenceStore:
    def __init__(
        self, sessions: sessionmaker[Session], *,
        gateway_secret: bytes, source_id: str,
    ):
        if not isinstance(gateway_secret, bytes) or len(gateway_secret) < 32:
            raise ValueError("core_evidence_gateway_key_invalid")
        if not isinstance(source_id, str) or re.fullmatch(
            r"[A-Za-z0-9_.-]{1,128}", source_id,
        ) is None:
            raise ValueError("core_evidence_gateway_source_invalid")
        self._sessions = sessions
        self._secret = gateway_secret
        self._source_id = source_id

    def record_attested(
        self, *, evidence_id: str,
        receipt: VerifiedProviderUsageReceipt,
        gateway_signature: str,
    ) -> bool:
        """One immutable evidence ID. Duplicate is idempotent, conflict denied."""
        if not isinstance(receipt, VerifiedProviderUsageReceipt):
            raise QuotaDenied("core_evidence_receipt_invalid")
        expected = sign_verified_gateway_attestation(
            evidence_id=evidence_id, source_id=self._source_id,
            receipt=receipt, secret=self._secret,
        )
        if (
            not isinstance(gateway_signature, str)
            or not hmac.compare_digest(expected, gateway_signature)
        ):
            raise QuotaDenied("core_evidence_gateway_signature_invalid")
        canonical = _canonical(evidence_id, self._source_id, receipt)
        fingerprint = hashlib.sha256(canonical).hexdigest()
        with self._sessions.begin() as db:
            existing = db.get(TrustedProviderEvidenceRecord, evidence_id)
            if existing is not None:
                if existing.canonical_sha256 != fingerprint:
                    raise QuotaDenied("core_evidence_immutable_conflict")
                return False
            db.add(TrustedProviderEvidenceRecord(
                evidence_id=evidence_id, source_id=self._source_id,
                tenant_id=receipt.tenant_id, unit_id=receipt.unit_id,
                request_id=receipt.request_id, provider=receipt.provider,
                model=receipt.model, input_tokens=receipt.input_tokens,
                output_tokens=receipt.output_tokens,
                cost_usd=(
                    str(receipt.provider_cost_usd)
                    if receipt.provider_cost_usd is not None else None
                ), evidence_digest=receipt.evidence_digest,
                no_charge=receipt.no_charge, canonical_sha256=fingerprint,
                accepted_at=datetime.now(UTC),
            ))
            try:
                db.flush()
            except IntegrityError as exc:
                raise QuotaDenied("core_evidence_concurrent_conflict") from exc
        return True

    def verify(
        self, *, evidence_id: str, request_id: str,
        tenant_id: str, unit_id: str,
    ) -> VerifiedProviderUsageReceipt:
        """Retrieve only an already-attested exact-scoped immutable receipt."""
        if any(
            not isinstance(value, str) or
            re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value) is None
            for value in (evidence_id, request_id, tenant_id, unit_id)
        ):
            raise QuotaDenied("core_evidence_scope_invalid")
        with self._sessions() as db:
            row = db.scalar(select(TrustedProviderEvidenceRecord).where(
                TrustedProviderEvidenceRecord.evidence_id == evidence_id,
                TrustedProviderEvidenceRecord.source_id == self._source_id,
                TrustedProviderEvidenceRecord.request_id == request_id,
                TrustedProviderEvidenceRecord.tenant_id == tenant_id,
                TrustedProviderEvidenceRecord.unit_id == unit_id,
            ))
            if row is None:
                raise QuotaDenied("core_evidence_not_found")
            return VerifiedProviderUsageReceipt(
                provider=row.provider, model=row.model, request_id=row.request_id,
                tenant_id=row.tenant_id, unit_id=row.unit_id,
                input_tokens=row.input_tokens, output_tokens=row.output_tokens,
                provider_cost_usd=Decimal(row.cost_usd)
                if row.cost_usd is not None else None,
                evidence_digest=row.evidence_digest, no_charge=row.no_charge,
            )
