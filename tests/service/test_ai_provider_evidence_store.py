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


def test_verified_signed_source_is_mandatory_before_gateway_acceptance(store):
    import json
    from datetime import UTC, datetime

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from core.ai_provider_source_verifier import ProviderSigningPolicy

    ledger, _ = store
    key = Ed25519PrivateKey.generate()
    pinned = ProviderSigningPolicy(
        issuer="signed-provider-ci",
        public_key=key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        ),
    )
    now = datetime.now(UTC)
    raw = json.dumps({
        "issuer": "signed-provider-ci",
        "request_id": "req-a", "tenant_id": "tenant-a", "unit_id": "unit-a",
        "provider": "gemini", "model": "gemini-model",
        "input_tokens": 100, "output_tokens": 50,
        "cost_usd": "0.0025", "no_charge": False,
        "observed_at": int(now.timestamp()),
    }, sort_keys=True, separators=(",", ":")).encode()
    signed = key.sign(b"FM_PROVIDER_USAGE_SOURCE_V1\n" + raw)
    with pytest.raises(QuotaDenied, match="provider_source_unauthenticated"):
        ledger.record_verified_source(
            evidence_id="provider-signed-1", provider_payload=raw,
            provider_signature=b"", source_policy=pinned,
            expected_request_id="req-a", expected_tenant_id="tenant-a",
            expected_unit_id="unit-a", at=now,
        )
    with pytest.raises(QuotaDenied):
        ledger.record_verified_source(
            evidence_id="provider-signed-1", provider_payload=raw,
            provider_signature=signed, source_policy=pinned,
            expected_request_id="req-a", expected_tenant_id="foreign",
            expected_unit_id="unit-a", at=now,
        )
    assert ledger.record_verified_source(
        evidence_id="provider-signed-1", provider_payload=raw,
        provider_signature=signed, source_policy=pinned,
        expected_request_id="req-a", expected_tenant_id="tenant-a",
        expected_unit_id="unit-a", at=now,
    )
    evidence = ledger.verify(
        evidence_id="provider-signed-1", request_id="req-a",
        tenant_id="tenant-a", unit_id="unit-a",
    )
    assert evidence.input_tokens + evidence.output_tokens == 150
