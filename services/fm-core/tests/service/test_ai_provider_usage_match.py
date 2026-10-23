"""Signed provider-source reconciliation with FM's immutable per-attempt ledger."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_provider_request_reconciliation import (
    SignedAttemptEvidence,
    reconcile_signed_provider_request,
)
from core.ai_provider_source_verifier import ProviderSigningPolicy
from core.ai_provider_usage_match import match_signed_provider_attempt
from core.ai_quota_store import QuotaDenied
from core.ai_usage_ledger import AIUsageRecord


@pytest.fixture
def ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'provider-usage.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(AIUsageRecord(
            event_id="attempt-1", tenant_id="tenant-a", unit_id="unit-a",
            request_id="req-1", correlation_id="corr", capability="text",
            provider="verified-provider", model="model-a", route_reason="initial",
            fallback_used=False, fallback_reason=None,
            input_tokens=100, output_tokens=50, cached_tokens=None,
            latency_ms=20, outcome="success", cost_decimal="0.005",
            currency="USD", cost_origin="estimated", price_snapshot_id="p1",
            event_time=datetime(2026, 10, 22, 12, tzinfo=UTC),
        ))
    yield sessions
    engine.dispose()


def signed_statement(*, overrides=None):
    now = datetime.now(UTC)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    policy = ProviderSigningPolicy(
        issuer="provider-statement-fixture", public_key=public,
        allowed_providers=frozenset({"verified-provider"}),
    )
    statement = {
        "issuer": policy.issuer, "request_id": "req-1", "tenant_id": "tenant-a",
        "unit_id": "unit-a", "provider": "verified-provider",
        "model": "model-a", "input_tokens": 100, "output_tokens": 50,
        "cost_usd": "0.006", "no_charge": False, "observed_at": int(now.timestamp()),
    }
    statement.update(overrides or {})
    raw = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    signature = private.sign(b"FM_PROVIDER_USAGE_SOURCE_V1\n" + raw)
    return policy, raw, signature, now


def check(sessions, policy, raw, signature, now, **scope):
    args = {
        "sessions": sessions, "source_payload": raw, "source_signature": signature,
        "source_policy": policy, "tenant_id": "tenant-a", "unit_id": "unit-a",
        "request_id": "req-1", "at": now,
    }
    args.update(scope)
    return match_signed_provider_attempt(**args)


def test_exact_signed_source_can_match_single_attempt_without_asserting_invoice(ledger):
    policy, raw, signature, now = signed_statement()
    matched = check(ledger, policy, raw, signature, now)
    assert matched.attempt_id == "attempt-1"
    assert matched.status == "signed_statement_matches_single_attempt"
    assert matched.invoice_verified is False
    assert matched.provider_statement_cost_usd == Decimal("0.006")
    assert matched.internally_estimated_cost_usd == Decimal("0.005")


@pytest.mark.parametrize("tamper", [
    {"input_tokens": 99}, {"output_tokens": 51},
    {"model": "other-model"},
])
def test_signed_but_inconsistent_statement_cannot_be_reconciled(ledger, tamper):
    policy, raw, signature, now = signed_statement(overrides=tamper)
    with pytest.raises(ControlPlaneError, match="provider_match_mismatch"):
        check(ledger, policy, raw, signature, now)


def test_signed_statement_from_unapproved_provider_is_denied_before_matching(ledger):
    policy, raw, signature, now = signed_statement(
        overrides={"provider": "other-provider"},
    )
    with pytest.raises(QuotaDenied, match="provider_source_statement_invalid"):
        check(ledger, policy, raw, signature, now)


def test_fallback_multi_attempt_and_no_charge_are_separate_paths(ledger):
    policy, raw, signature, now = signed_statement()
    with ledger.begin() as db:
        db.add(AIUsageRecord(
            event_id="attempt-2", tenant_id="tenant-a", unit_id="unit-a",
            request_id="req-1", correlation_id="corr", capability="text",
            provider="verified-provider", model="model-a", route_reason="fallback",
            fallback_used=True, fallback_reason="temporary",
            input_tokens=None, output_tokens=None, cached_tokens=None,
            latency_ms=10, outcome="transient_failure", cost_decimal=None,
            currency="XXX", cost_origin="unavailable", price_snapshot_id="p1",
            event_time=now,
        ))
    with pytest.raises(ControlPlaneError, match="provider_match_ambiguous_attempts"):
        check(ledger, policy, raw, signature, now)
    no_charge_policy, no_charge_body, no_charge_sig, at = signed_statement(
        overrides={"no_charge": True, "input_tokens": 0,
                   "output_tokens": 0, "cost_usd": "0"},
    )
    with pytest.raises(ControlPlaneError, match="no_charge_separate"):
        check(ledger, no_charge_policy, no_charge_body, no_charge_sig, at)


def test_bad_signature_wrong_tenant_and_stale_source_are_not_evidence(ledger):
    policy, raw, signature, now = signed_statement()
    with pytest.raises(QuotaDenied):
        check(ledger, policy, raw, b"", now)
    with pytest.raises(QuotaDenied):
        check(ledger, policy, raw, signature, now, tenant_id="tenant-b")
    with pytest.raises(QuotaDenied):
        check(ledger, policy, raw, signature, now.replace(year=now.year + 1))


def test_cost_unknown_stays_unknown_even_with_verified_usage_statement(ledger):
    policy, raw, signature, now = signed_statement()
    with ledger.begin() as db:
        row = db.scalar(select(AIUsageRecord).where(
            AIUsageRecord.event_id == "attempt-1",
        ))
        row.cost_decimal = None
        row.currency = "XXX"
    match = check(ledger, policy, raw, signature, now)
    assert match.internally_estimated_cost_usd is None
    assert match.provider_statement_cost_usd == Decimal("0.006")
    assert match.invoice_verified is False


def _insert_attempt(
    db, *, event_id: str, provider="verified-provider", model="model-a",
    inp=100, out=50, outcome="success", fallback=False,
):
    db.add(AIUsageRecord(
        event_id=event_id, tenant_id="tenant-a", unit_id="unit-a",
        request_id="req-1", correlation_id="corr", capability="text",
        provider=provider, model=model, route_reason="fallback" if fallback else "initial",
        fallback_used=fallback, fallback_reason="retry" if fallback else None,
        input_tokens=inp, output_tokens=out, cached_tokens=None,
        latency_ms=20, outcome=outcome, cost_decimal=None,
        currency="XXX", cost_origin="unavailable", price_snapshot_id="p1",
        event_time=datetime.now(UTC),
    ))


def test_signed_provider_receipt_identifies_unique_successful_fallback(ledger):
    policy, raw, signature, now = signed_statement()
    with ledger.begin() as db:
        first = db.get(AIUsageRecord, "attempt-1")
        first.fallback_used = True
        first.fallback_reason = "other-provider-failed-first"
        _insert_attempt(
            db, event_id="attempt-early-failed", provider="different-provider",
            outcome="transient_failure", inp=None, out=None,
        )
    matched = check(ledger, policy, raw, signature, now)
    assert matched.attempt_id == "attempt-1"
    assert matched.matched_fallback_attempt is True
    assert matched.invoice_verified is False


def test_duplicate_matching_attempts_fail_closed_without_attribution(ledger):
    policy, raw, signature, now = signed_statement()
    with ledger.begin() as db:
        _insert_attempt(db, event_id="attempt-cloned", fallback=True)
    with pytest.raises(ControlPlaneError, match="provider_match_ambiguous_attempts"):
        check(ledger, policy, raw, signature, now)


def test_unknown_usage_on_same_provider_blocks_false_unique_match(ledger):
    policy, raw, signature, now = signed_statement()
    with ledger.begin() as db:
        _insert_attempt(
            db, event_id="attempt-unmetered", inp=None, out=None, fallback=True,
        )
    with pytest.raises(ControlPlaneError, match="provider_match_ambiguous_attempts"):
        check(ledger, policy, raw, signature, now)


def test_signed_statement_never_matches_truncated_attempt_history(ledger):
    policy, raw, signature, now = signed_statement()
    with ledger.begin() as db:
        for i in range(101):
            _insert_attempt(
                db, event_id=f"attempt-excess-{i}", provider="different-provider",
                outcome="transient_failure", inp=None, out=None,
            )
    with pytest.raises(ControlPlaneError, match="provider_match_unbounded_attempts"):
        check(ledger, policy, raw, signature, now)


def _batch(sessions, *evidences):
    return reconcile_signed_provider_request(
        sessions=sessions,
        statements=tuple(SignedAttemptEvidence(
            payload=body, signature=signature, policy=policy,
        ) for policy, body, signature, _ in evidences),
        tenant_id="tenant-a", unit_id="unit-a", request_id="req-1",
        at=evidences[0][3],
    )


def test_request_reconciliation_never_confuses_statement_with_invoice(ledger):
    signed = signed_statement()
    original = ledger()
    before = original.scalar(select(AIUsageRecord).where(
        AIUsageRecord.event_id == "attempt-1",
    ))
    result = _batch(ledger, signed)
    assert result.attempts_observed == 1
    assert result.statements_matched == 1
    assert result.unmatched_attempts == 0
    assert result.all_attempts_matched is True
    assert result.cost_disagreement_attempts == 1
    assert result.internal_known_cost_usd_subtotal == Decimal("0.005")
    assert result.statement_known_cost_usd_subtotal == Decimal("0.006")
    assert result.needs_attention is True
    assert result.invoice_verified is False
    assert result.quota_recovery_authorized is False
    with ledger() as check:
        after = check.get(AIUsageRecord, "attempt-1")
        assert after.cost_decimal == before.cost_decimal
        assert after.input_tokens == before.input_tokens
    original.close()


def test_multi_provider_fallback_reconciles_every_attempt_without_mutation(ledger):
    first = signed_statement(overrides={"cost_usd": "0.005"})
    second = signed_statement(overrides={
        "provider": "other-provider", "model": "model-b",
        "input_tokens": 200, "output_tokens": 20, "cost_usd": "0.008",
    })
    # The second statement source may attest only its explicitly allowed vendor.
    private = Ed25519PrivateKey.generate()
    policy = ProviderSigningPolicy(
        issuer="second-issuer",
        public_key=private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        ),
        allowed_providers=frozenset({"other-provider"}),
    )
    raw = json.loads(second[1])
    raw["issuer"] = policy.issuer
    payload = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    second = (policy, payload, private.sign(
        b"FM_PROVIDER_USAGE_SOURCE_V1\n" + payload,
    ), first[3])
    with ledger.begin() as db:
        _insert_attempt(
            db, event_id="attempt-2", provider="other-provider",
            model="model-b", inp=200, out=20, fallback=True,
        )
        db.get(AIUsageRecord, "attempt-2").cost_decimal = "0.008"
        db.get(AIUsageRecord, "attempt-2").currency = "USD"
    result = _batch(ledger, first, second)
    assert result.attempts_observed == 2
    assert result.statements_matched == 2
    assert result.unmatched_attempts == 0
    assert result.unknown_usage_attempts == 0
    assert result.internal_cost_unknown_attempts == 0
    assert result.statement_cost_unknown_attempts == 0
    assert result.internal_known_cost_usd_subtotal == Decimal("0.013")
    assert result.statement_known_cost_usd_subtotal == Decimal("0.013")
    assert result.cost_disagreement_attempts == 0
    assert result.all_attempts_matched is True
    assert result.needs_attention is False
    assert result.invoice_verified is False
    assert result.quota_recovery_authorized is False


def test_partial_failed_fallback_and_unknown_cost_remain_needs_attention(ledger):
    signed = signed_statement()
    with ledger.begin() as db:
        _insert_attempt(
            db, event_id="attempt-transient-failure", provider="other-provider",
            outcome="transient_failure", inp=None, out=None, fallback=True,
        )
        db.get(AIUsageRecord, "attempt-1").cost_decimal = None
        db.get(AIUsageRecord, "attempt-1").currency = "XXX"
    result = _batch(ledger, signed)
    assert result.attempts_observed == 2
    assert result.statements_matched == 1
    assert result.unmatched_attempts == 1
    assert result.unknown_usage_attempts == 1
    assert result.internal_cost_unknown_attempts == 2
    assert result.internal_known_cost_usd_subtotal == Decimal(0)
    assert result.needs_attention is True


def test_duplicate_sources_replay_cannot_double_count_request(ledger):
    signed = signed_statement()
    with pytest.raises(ControlPlaneError, match="reconciliation_duplicate_attempt"):
        _batch(ledger, signed, signed)


def test_corrupt_batch_unsigned_and_cross_tenant_are_denied(ledger):
    signed = signed_statement()
    source = SignedAttemptEvidence(
        payload=signed[1], signature=signed[2], policy=signed[0],
    )
    args = {"sessions": ledger, "tenant_id": "tenant-a", "unit_id": "unit-a",
            "request_id": "req-1", "at": signed[3]}
    with pytest.raises(ControlPlaneError, match="invalid_batch"):
        reconcile_signed_provider_request(statements=(), **args)
    with pytest.raises(ControlPlaneError, match="invalid_batch"):
        reconcile_signed_provider_request(statements=(source,) * 101, **args)
    with pytest.raises(ControlPlaneError, match="invalid_source"):
        reconcile_signed_provider_request(statements=(object(),), **args)
    with pytest.raises(QuotaDenied):
        reconcile_signed_provider_request(statements=(
            SignedAttemptEvidence(
                payload=source.payload, signature=b"", policy=source.policy,
            ),
        ), **args)
    with pytest.raises(QuotaDenied):
        reconcile_signed_provider_request(
            statements=(source,), **{**args, "tenant_id": "foreign-tenant"},
        )


def test_request_reconciliation_denies_unknown_currency_with_known_cost(ledger):
    signed = signed_statement()
    with ledger.begin() as db:
        db.get(AIUsageRecord, "attempt-1").currency = "BRL"
    with pytest.raises(ControlPlaneError, match="currency_mismatch"):
        _batch(ledger, signed)
