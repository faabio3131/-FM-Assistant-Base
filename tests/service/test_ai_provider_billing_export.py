"""F3 adversarial provider export readbacks, no external credentials or billing."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_provider_billing_export import (
    ProviderExportPolicy,
    ProviderExportRecord,
    readback_provider_export_attempt,
)
from core.ai_usage_ledger import AIUsageRecord

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
POLICY = ProviderExportPolicy(
    provider="openai-compatible-vendor", adapter="openai_compatible",
    account_ref="fm-business-account",
)


class FakePort:
    def __init__(self, record):
        self.record = record
        self.calls = []

    def read_attempt(self, **kwargs):
        self.calls.append(kwargs)
        return self.record


@pytest.fixture
def ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'billing-export.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(AIUsageRecord(
            event_id="evt-one", attempt_id="attempt-one",
            tenant_id="fm-tenant", unit_id="unit-1",
            request_id="req-one", correlation_id="correlation",
            capability="text", provider="openai-compatible-vendor",
            model="model-x", route_reason="initial", fallback_used=False,
            fallback_reason=None, input_tokens=100, output_tokens=50,
            cached_tokens=None, latency_ms=100, outcome="success",
            cost_decimal="0.005", currency="USD", cost_origin="estimated",
            price_snapshot_id="price", event_time=NOW,
        ))
    yield sessions
    engine.dispose()


@pytest.fixture
def export_record():
    return ProviderExportRecord(
        provider=POLICY.provider, account_ref=POLICY.account_ref,
        tenant_id="fm-tenant", unit_id="unit-1",
        request_id="req-one", attempt_id="attempt-one",
        model="model-x", source_ref="readback-unique",
        observed_at=NOW - timedelta(seconds=12),
        usage={"prompt_tokens": 100, "completion_tokens": 50},
        cost_usd="0.005",
    )


def inspect(sessions, record, policy=POLICY, **kw):
    return readback_provider_export_attempt(
        sessions=sessions, port=FakePort(record), policy=policy,
        tenant_id="fm-tenant", unit_id="unit-1",
        request_id="req-one", attempt_id="attempt-one", now=NOW, **kw,
    )


def test_openai_compatible_export_matches_but_is_never_invoice(ledger, export_record):
    report = inspect(ledger, export_record)
    assert report.usage_matches is True
    assert report.cost_matches is True
    assert report.needs_attention is False
    assert report.status == "observational_match"
    assert report.provider_invoice_verified is False
    assert report.provider_signature_verified is False
    assert report.quota_recovery_authorized is False


def test_gemini_mapping_and_provider_policy_configurable(ledger, export_record):
    policy = ProviderExportPolicy(
        provider="openai-compatible-vendor",
        adapter="gemini", account_ref=POLICY.account_ref,
    )
    record = replace(export_record, usage={
        "promptTokenCount": 100, "candidatesTokenCount": 50,
        "cachedContentTokenCount": 0,
    })
    assert inspect(ledger, record, policy).status == "observational_match"


def test_missing_export_never_means_no_charge(ledger):
    report = inspect(ledger, None)
    assert report.needs_attention is True
    assert report.report_cost_usd is None
    assert report.internal_cost_usd == Decimal("0.005")
    assert report.status == "missing_provider_export"


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "other-tenant"), ("unit_id", "other-unit"),
    ("request_id", "other-request"), ("attempt_id", "other-attempt"),
    ("account_ref", "other-account"), ("provider", "another-provider"),
    ("model", "another-model"),
])
def test_export_scope_and_identity_forgery_denied(ledger, export_record, field, value):
    with pytest.raises(ControlPlaneError, match="export_scope_mismatch"):
        inspect(ledger, replace(export_record, **{field: value}))


@pytest.mark.parametrize("field,value", [
    ("prompt_tokens", True), ("prompt_tokens", "100"),
    ("prompt_tokens", -1), ("completion_tokens", 2.5),
    ("completion_tokens", 2_000_000_001),
])
def test_ambiguous_metering_never_coerces(ledger, export_record, field, value):
    usage = dict(export_record.usage)
    usage[field] = value
    with pytest.raises(ControlPlaneError, match="export_meter_invalid"):
        inspect(ledger, replace(export_record, usage=usage))


def test_unknown_and_discrepant_values_stay_actionable(ledger, export_record):
    missing = inspect(ledger, replace(export_record, usage={
        "prompt_tokens": 100,
    }, cost_usd=None))
    assert missing.usage_matches is None
    assert missing.cost_matches is None
    assert missing.needs_attention is True
    mismatch = inspect(ledger, replace(export_record,
        usage={"prompt_tokens": 99, "completion_tokens": 50}, cost_usd="0.006"))
    assert mismatch.usage_matches is False
    assert mismatch.cost_matches is False
    assert mismatch.needs_attention is True


@pytest.mark.parametrize("cost", ["nan", "Infinity", "-0.001", "not-a-number", "9e9999"])
def test_nonfinite_negative_and_invalid_cost_denied(ledger, export_record, cost):
    with pytest.raises(ControlPlaneError, match="export_cost_invalid"):
        inspect(ledger, replace(export_record, cost_usd=cost))


def test_expired_and_future_snapshot_denied(ledger, export_record):
    with pytest.raises(ControlPlaneError, match="stale_or_future"):
        inspect(ledger, replace(export_record,
            observed_at=NOW-timedelta(days=2)))
    with pytest.raises(ControlPlaneError, match="stale_or_future"):
        inspect(ledger, replace(export_record,
            observed_at=NOW+timedelta(seconds=16)))


def test_requires_local_physical_attempt_before_fetch_and_denies_cross_tenant(ledger, export_record):
    port = FakePort(export_record)
    with pytest.raises(ControlPlaneError, match="attempt_not_unique"):
        readback_provider_export_attempt(
            sessions=ledger, port=port, policy=POLICY,
            tenant_id="foreign", unit_id="unit-1",
            request_id="req-one", attempt_id="attempt-one", now=NOW,
        )
    assert port.calls == []


def test_rejects_wrong_account_policy_and_invalid_adapter(ledger, export_record):
    with pytest.raises(ControlPlaneError, match="export_provider_mismatch"):
        inspect(ledger, export_record, ProviderExportPolicy(
            provider="other", adapter="gemini", account_ref=POLICY.account_ref,
        ))
    with pytest.raises(ControlPlaneError, match="export_policy_invalid"):
        ProviderExportPolicy(
            provider="vendor", adapter="bogus", account_ref="account",
        )


def test_remains_read_only_in_database(ledger, export_record):
    report = inspect(ledger, export_record)
    with ledger() as db:
        row = db.get(AIUsageRecord, "evt-one")
        assert row.input_tokens == 100
        assert row.output_tokens == 50
        assert row.cost_decimal == "0.005"
    assert not report.quota_recovery_authorized
