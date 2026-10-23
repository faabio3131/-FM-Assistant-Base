"""Minimal F3 construction smoke: immutable provider import and scoped readback."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_command_authority import VerifiedCommandAdmin
from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_provider_billing_export import ProviderExportPolicy, ProviderExportRecord
from core.ai_provider_export_store import PersistentProviderExportStore
from core.ai_usage_ledger import AIUsageRecord


def test_import_readback_idempotent_and_conflict_fails_closed(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'provider-import.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with sessions.begin() as db:
        db.add(AIUsageRecord(
            event_id="evt-1", attempt_id="attempt-1",
            tenant_id="tenant-fm", unit_id="unit-1", request_id="req-1",
            correlation_id="corr-1", capability="text",
            provider="test-vendor", model="test-model", route_reason="primary",
            fallback_used=False, fallback_reason=None,
            input_tokens=12, output_tokens=5, cached_tokens=None,
            latency_ms=10, outcome="success",
            cost_decimal="0.004", currency="USD", cost_origin="estimated",
            price_snapshot_id="price-1", event_time=now,
        ))
    principal = VerifiedCommandAdmin(
        user_id="fm-admin", session_id="admin-session",
        token_id="unique-jwt-jti", issued_at=int(now.timestamp()),
        expires_at=int(now.timestamp()) + 300,
        step_up_at=int(now.timestamp()),
        permissions=frozenset({"admin.acessar"}),
    )
    policy = ProviderExportPolicy(
        provider="test-vendor", adapter="openai_compatible",
        account_ref="fm-account", max_age_seconds=31 * 86400,
    )
    source = ProviderExportRecord(
        provider="test-vendor", model="test-model",
        tenant_id="tenant-fm", unit_id="unit-1", request_id="req-1",
        attempt_id="attempt-1", account_ref="fm-account",
        source_ref="export-123", observed_at=now-timedelta(minutes=5),
        usage={"prompt_tokens": 12, "completion_tokens": 5},
        cost_usd="0.005",
    )
    store = PersistentProviderExportStore(sessions)
    assert store.import_snapshot(
        policy=policy, record=source, principal=principal, now=now,
    ) == "created"
    result = store.compare(
        tenant_id="tenant-fm", unit_id="unit-1", request_id="req-1",
        attempt_id="attempt-1",
    )
    assert result is not None
    assert result.usage_matches is True
    assert result.cost_matches is False
    assert result.needs_attention is True
    assert result.provider_invoice_verified is False
    assert result.quota_recovery_authorized is False
    assert store.import_snapshot(
        policy=policy, record=source, principal=principal, now=now,
    ) == "already_recorded"
    with pytest.raises(ControlPlaneError, match="conflicting_snapshot"):
        store.import_snapshot(
            policy=policy, record=replace(source, cost_usd="0.006"),
            principal=principal, now=now,
        )
    assert store.compare(
        tenant_id="foreign", unit_id="unit-1", request_id="req-1",
        attempt_id="attempt-1",
    ) is None
    with sessions() as db:
        row = db.get(AIUsageRecord, "evt-1")
        assert row.cost_decimal == "0.004"
    engine.dispose()
