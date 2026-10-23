"""Untrusted payload cannot fabricate independently signed provider evidence."""
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.ai_provider_source_verifier import (
    ProviderSigningPolicy,
    verified_signed_usage_source,
)
from core.ai_quota_store import QuotaDenied


def _fixture():
    from cryptography.hazmat.primitives import serialization

    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    now = datetime.now(UTC)
    data = {
        "issuer": "signed-provider-fixture",
        "request_id": "request-1", "tenant_id": "tenant-1",
        "unit_id": "unit-1", "provider": "verified-source",
        "model": "verified-model", "input_tokens": 120,
        "output_tokens": 30, "cost_usd": "0.003",
        "no_charge": False, "observed_at": int(now.timestamp()),
    }
    body = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    signature = private.sign(b"FM_PROVIDER_USAGE_SOURCE_V1\n" + body)
    policy = ProviderSigningPolicy(
        issuer="signed-provider-fixture", public_key=public,
        allowed_providers=frozenset({"verified-source"}),
    )
    return private, policy, body, signature, now


def _verify(policy, body, signature, now, *, tenant="tenant-1"):
    return verified_signed_usage_source(
        payload=body, signature=signature, policy=policy,
        expected_request_id="request-1", expected_tenant_id=tenant,
        expected_unit_id="unit-1", at=now,
    )


def test_valid_pinned_signed_usage_binds_request_scope_and_exact_tokens():
    _, policy, body, signature, now = _fixture()
    receipt = _verify(policy, body, signature, now)
    assert receipt.input_tokens == 120
    assert receipt.output_tokens == 30
    assert len(receipt.evidence_digest) == 64


def test_forged_body_unknown_key_wrong_scope_and_stale_statement_fail_closed():
    private, policy, body, signature, now = _fixture()
    for attempted in (
        (policy, body.replace(b"120", b"190"), signature, now, "tenant-1"),
        (policy, body, b"x" * 64, now, "tenant-1"),
        (policy, body, signature, now, "foreign-tenant"),
        (replace(policy, issuer="imposter"), body, signature, now, "tenant-1"),
        (policy, body, signature, now.replace(year=now.year + 1), "tenant-1"),
    ):
        with pytest.raises(QuotaDenied):
            _verify(attempted[0], attempted[1], attempted[2],
                    attempted[3], tenant=attempted[4])
    # A signature for a different operation cannot substitute for this request.
    other_body = body.replace(b"request-1", b"request-2")
    other_sig = private.sign(b"FM_PROVIDER_USAGE_SOURCE_V1\n" + other_body)
    with pytest.raises(QuotaDenied):
        _verify(policy, other_body, other_sig, now)


def test_unsigned_generic_provider_response_never_counts_as_signed_evidence():
    _, policy, body, _, now = _fixture()
    with pytest.raises(QuotaDenied, match="provider_source_unauthenticated"):
        _verify(policy, body, b"", now)

def test_valid_signature_cannot_impersonate_another_provider():
    private, policy, body, _, now = _fixture()
    attacker_payload = json.loads(body)
    attacker_payload["provider"] = "another-provider"
    swapped = json.dumps(
        attacker_payload, sort_keys=True, separators=(",", ":"),
    ).encode()
    valid_for_same_issuer = private.sign(b"FM_PROVIDER_USAGE_SOURCE_V1\\n" + swapped)
    with pytest.raises(QuotaDenied, match="provider_source_statement_invalid"):
        _verify(policy, swapped, valid_for_same_issuer, now)
    # Adding the provider to an explicitly approved policy is the only valid
    # way to authorize a gateway that legitimately verifies multiple vendors.
    authorized = replace(
        policy, allowed_providers=frozenset({"verified-source", "another-provider"}),
    )
    assert _verify(authorized, swapped, valid_for_same_issuer, now).provider == (
        "another-provider"
    )


def test_signing_policy_rejects_missing_or_mutable_provider_grants():
    _, policy, _, _, _ = _fixture()
    for invalid in (frozenset(), {"verified-source"}, frozenset({""})):
        with pytest.raises(ValueError, match="provider_source_policy_invalid"):
            replace(policy, allowed_providers=invalid)
