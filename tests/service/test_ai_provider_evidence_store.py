"""FM evidence gateway attestation and immutable Core evidence retention."""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase
from core.ai_provider_evidence_store import (
    TrustedProviderEvidenceRecord,
    TrustedProviderEvidenceStore,
    sign_verified_gateway_attestation,
)
from core.ai_quota_store import QuotaDenied
from core.ai_verified_usage_receipt import VerifiedProviderUsageReceipt

GATEWAY_SECRET = b"synthetic-evidence-connector-secret-key-very-long"
SOURCE = "fm-evidence-connector"


def _receipt(*, tenant="tenant-a", tokens=100):
    return VerifiedProviderUsageReceipt(
        provider="gemini", model="gemini-model",
        request_id="req-a", tenant_id=tenant, unit_id="unit-a",
        input_tokens=tokens, output_tokens=50,
        provider_cost_usd=Decimal("0.0025"),
        evidence_digest="a" * 64,
    )


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'evidence.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    try:
        yield TrustedProviderEvidenceStore(
            sessions, source_id=SOURCE, gateway_secret=GATEWAY_SECRET,
        ), sessions
    finally:
        engine.dispose()


def test_only_gateway_attested_evidence_is_persisted_and_readable(store):
    ledger, sessions = store
    receipt = _receipt()
    signature = sign_verified_gateway_attestation(
        evidence_id="proof-1", source_id=SOURCE,
        receipt=receipt, secret=GATEWAY_SECRET,
    )
    with pytest.raises(QuotaDenied, match="core_evidence_gateway_signature_invalid"):
        ledger.record_attested(
            evidence_id="proof-1", receipt=receipt, gateway_signature="a" * 64,
        )
    assert ledger.record_attested(
        evidence_id="proof-1", receipt=receipt, gateway_signature=signature,
    )
    assert not ledger.record_attested(
        evidence_id="proof-1", receipt=receipt, gateway_signature=signature,
    )
    assert ledger.verify(
        evidence_id="proof-1", request_id="req-a",
        tenant_id="tenant-a", unit_id="unit-a",
    ) == receipt
    with sessions() as db:
        assert db.get(TrustedProviderEvidenceRecord, "proof-1").source_id == SOURCE
    with pytest.raises(QuotaDenied, match="core_evidence_not_found"):
        ledger.verify(
            evidence_id="proof-1", request_id="req-a",
            tenant_id="foreign", unit_id="unit-a",
        )


def test_immutable_evidence_cannot_switch_tenant_or_token_amount(store):
    ledger, _ = store
    receipt = _receipt()
    ledger.record_attested(
        evidence_id="immutable-1", receipt=receipt,
        gateway_signature=sign_verified_gateway_attestation(
            evidence_id="immutable-1", source_id=SOURCE,
            receipt=receipt, secret=GATEWAY_SECRET,
        ),
    )
    altered = _receipt(tokens=101)
    with pytest.raises(QuotaDenied, match="core_evidence_immutable_conflict"):
        ledger.record_attested(
            evidence_id="immutable-1", receipt=altered,
            gateway_signature=sign_verified_gateway_attestation(
                evidence_id="immutable-1", source_id=SOURCE,
                receipt=altered, secret=GATEWAY_SECRET,
            ),
        )
    assert ledger.verify(
        evidence_id="immutable-1", request_id="req-a",
        tenant_id="tenant-a", unit_id="unit-a",
    ) == receipt


def test_missing_record_never_bypasses_command_recovery(store):
    ledger, _ = store
    with pytest.raises(QuotaDenied):
        ledger.verify(
            evidence_id="missing", request_id="req-a",
            tenant_id="tenant-a", unit_id="unit-a",
        )
