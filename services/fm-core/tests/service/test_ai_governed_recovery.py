"""Command JWT + trusted provider evidence boundary for recovery."""
from datetime import UTC, datetime
from decimal import Decimal

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from core.ai_command_authority import CommandAuthorityDenied, CommandTrustPolicy
from core.ai_governed_recovery import GovernedRecoveryCommand, execute_governed_recovery
from core.ai_quota_store import QuotaDenied
from core.ai_verified_usage_receipt import VerifiedProviderUsageReceipt


def _identity():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return key, CommandTrustPolicy(
        issuer="fm-command-internal", audience="fm-core-recovery", public_key_pem=public_key,
    )


def _token(key, *, tenant_admin=False):
    now = int(datetime.now(UTC).timestamp())
    return jwt.encode({
        "iss": "fm-command-internal", "aud": "fm-core-recovery",
        "sub": "human-1", "session_id": "session-1",
        "jti": "fresh-one-time-command-jti-123",
        "iat": now, "nbf": now, "exp": now + 120,
        "step_up_at": now, "actor_type": "human",
        "role": "tenant_admin" if tenant_admin else "platform_admin",
        "scope": "fm_core_platform",
        "permissions": ["core.ai.admin.mutate"],
    }, key, algorithm="RS256")


class FakeVerifier:
    def __init__(self, *, foreign=False):
        self.calls = 0
        self.foreign = foreign

    def verify(self, *, evidence_id, request_id, tenant_id, unit_id):
        self.calls += 1
        assert evidence_id == "provider-attestation-1"
        return VerifiedProviderUsageReceipt(
            provider="gemini", model="gemini-model",
            request_id=request_id,
            tenant_id="other-tenant" if self.foreign else tenant_id,
            unit_id=unit_id, input_tokens=20, output_tokens=10,
            provider_cost_usd=Decimal("0.002"),
            evidence_digest="a" * 64,
        )


class FakeLedger:
    def __init__(self):
        self.calls = 0

    def reconcile_verified_provider_receipt(self, **kwargs):
        self.calls += 1
        assert kwargs["receipt"].input_tokens == 20
        assert kwargs["principal"].user_id == "human-1"


def test_signed_recovery_calls_one_core_settlement_only():
    key, trust = _identity()
    proof, ledger = FakeVerifier(), FakeLedger()
    execute_governed_recovery(
        command=GovernedRecoveryCommand(
            request_id="request-1", tenant_id="tenant-1", unit_id="unit-1",
            evidence_id="provider-attestation-1",
            requests_revision=1, tokens_revision=1,
        ),
        bearer_token=_token(key), trust=trust, evidence=proof,
        ledger=ledger, at=datetime.now(UTC),
    )
    assert proof.calls == ledger.calls == 1


def test_forged_command_or_wrong_tenant_never_settles():
    key, trust = _identity()
    command = GovernedRecoveryCommand(
        request_id="request-1", tenant_id="tenant-1", unit_id="unit-1",
        evidence_id="provider-attestation-1",
        requests_revision=1, tokens_revision=1,
    )
    for token in (_token(key, tenant_admin=True), "not-a-token"):
        proof, ledger = FakeVerifier(), FakeLedger()
        with pytest.raises(CommandAuthorityDenied):
            execute_governed_recovery(
                command=command, bearer_token=token, trust=trust,
                evidence=proof, ledger=ledger, at=datetime.now(UTC),
            )
        assert proof.calls == ledger.calls == 0
    proof, ledger = FakeVerifier(foreign=True), FakeLedger()
    with pytest.raises(QuotaDenied, match="core_recovery_evidence_scope_mismatch"):
        execute_governed_recovery(
            command=command, bearer_token=_token(key), trust=trust,
            evidence=proof, ledger=ledger, at=datetime.now(UTC),
        )
    assert proof.calls == 1 and ledger.calls == 0
