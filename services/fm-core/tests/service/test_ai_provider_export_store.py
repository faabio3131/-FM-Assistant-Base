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
    before = store.coverage(
        tenant_id="tenant-fm", unit_id="unit-1",
        start_date=now.date(), end_date=now.date(), only_missing=True,
    )
    assert len(before["items"]) == 1
    assert before["items"][0]["export_status"] == "missing_provider_export"
    assert before["items"][0]["needs_attention"] is True
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
    after = store.coverage(
        tenant_id="tenant-fm", unit_id="unit-1",
        start_date=now.date(), end_date=now.date(),
    )
    assert len(after["items"]) == 1
    assert after["items"][0]["export_status"] == "needs_attention"
    assert after["items"][0]["cost_matches"] is False
    assert store.coverage(
        tenant_id="tenant-fm", unit_id="unit-1",
        start_date=now.date(), end_date=now.date(), only_missing=True,
    )["items"] == []
    assert store.coverage(
        tenant_id="other-tenant", unit_id="unit-1",
        start_date=now.date(), end_date=now.date(),
    )["items"] == []
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



def test_coverage_pagination_and_strict_scoping(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'coverage.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with sessions.begin() as db:
        for i in range(3):
            db.add(AIUsageRecord(
                event_id=f"evt-{i}", attempt_id=f"physical-{i}",
                tenant_id="tenant-fm" if i < 2 else "tenant-other",
                unit_id="unit-1", request_id=f"req-{i}",
                correlation_id=f"corr-{i}", capability="text",
                provider="provider-a", model="model-1",
                route_reason="primary", fallback_used=bool(i),
                fallback_reason="fallback" if i else None,
                input_tokens=None, output_tokens=None, cached_tokens=None,
                latency_ms=5, outcome="unknown", cost_decimal=None,
                currency="USD", cost_origin="unknown",
                price_snapshot_id="price-1", event_time=now,
            ))
    store = PersistentProviderExportStore(sessions)
    kwargs = {
        "tenant_id": "tenant-fm", "unit_id": "unit-1",
        "start_date": now.date(), "end_date": now.date(), "limit": 1,
    }
    first = store.coverage(**kwargs)
    assert len(first["items"]) == 1
    assert first["next_page"] == 1
    assert first["items"][0]["needs_attention"] is True
    assert first["items"][0]["cost_matches"] is None
    assert first["provider_invoice_verified"] is False
    second = store.coverage(**kwargs, page=1)
    assert second["next_page"] is None
    assert second["items"][0]["fallback"] is True
    with pytest.raises(ControlPlaneError, match="coverage_invalid"):
        store.coverage(**{**kwargs, "limit": True})
    with pytest.raises(ControlPlaneError, match="coverage_invalid"):
        store.coverage(**{**kwargs, "page": -1})
    with pytest.raises(ControlPlaneError, match="coverage_invalid"):
        store.coverage(**{**kwargs, "start_date": now.date() + timedelta(days=1)})
    engine.dispose()



def test_bounded_provider_batch_is_atomic_and_replay_safe(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'export-batch.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with sessions.begin() as db:
        for index in (1, 2):
            db.add(AIUsageRecord(
                event_id=f"evt-b{index}", attempt_id=f"attempt-b{index}",
                tenant_id="tenant-fm", unit_id="unit-1", request_id=f"req-b{index}",
                correlation_id=f"corr-b{index}", capability="text",
                provider="provider-a", model="model-a", route_reason="primary",
                fallback_used=False, fallback_reason=None,
                input_tokens=12, output_tokens=5, cached_tokens=None,
                latency_ms=10, outcome="success", cost_decimal="0.004",
                currency="USD", cost_origin="estimated",
                price_snapshot_id="price-1", event_time=now,
            ))
    principal = VerifiedCommandAdmin(
        user_id="fm-admin", session_id="admin-session",
        token_id="one-batch-jti", issued_at=int(now.timestamp()),
        expires_at=int(now.timestamp()) + 300, step_up_at=int(now.timestamp()),
        permissions=frozenset({"admin.acessar"}),
    )
    policy = ProviderExportPolicy(
        provider="provider-a", adapter="openai_compatible",
        account_ref="account-fm", max_age_seconds=31 * 86400,
    )
    records = tuple(
        ProviderExportRecord(
            provider="provider-a", model="model-a",
            tenant_id="tenant-fm", unit_id="unit-1",
            request_id=f"req-b{index}", attempt_id=f"attempt-b{index}",
            account_ref="account-fm", source_ref=f"vendor-export-b{index}",
            observed_at=now - timedelta(minutes=1),
            usage={"prompt_tokens": 12, "completion_tokens": 5},
            cost_usd="0.004",
        ) for index in (1, 2)
    )
    store = PersistentProviderExportStore(sessions)
    assert store.import_batch(
        policy=policy, records=records, principal=principal, now=now,
    ) == {"created": 2, "already_recorded": 0}
    assert store.import_batch(
        policy=policy, records=records, principal=principal, now=now,
    ) == {"created": 0, "already_recorded": 2}
    assert len(store.coverage(
        tenant_id="tenant-fm", unit_id="unit-1",
        start_date=now.date(), end_date=now.date(),
        only_missing=True,
    )["items"]) == 0
    with pytest.raises(ControlPlaneError, match="batch_duplicate"):
        store.import_batch(
            policy=policy, records=(records[0], records[0]),
            principal=principal, now=now,
        )
    with pytest.raises(ControlPlaneError, match="batch_scope_mismatch"):
        store.import_batch(
            policy=policy,
            records=(records[0], replace(records[1], tenant_id="tenant-other")),
            principal=principal, now=now,
        )
    with pytest.raises(ControlPlaneError, match="conflicting_snapshot"):
        store.import_batch(
            policy=policy,
            records=(records[0], replace(records[1], cost_usd="0.005")),
            principal=principal, now=now,
        )
    result = store.compare(
        tenant_id="tenant-fm", unit_id="unit-1",
        request_id="req-b2", attempt_id="attempt-b2",
    )
    assert result.cost_matches is True
    assert result.provider_invoice_verified is False
    engine.dispose()
