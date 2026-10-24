"""P01 F3/F9: request-wide fallback cost diagnostics, never vendor billing proof."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_command_authority import CommandTrustPolicy, VerifiedCommandAdmin
from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_finops_policy_api import finops_alert_policy_router
from core.ai_provider_billing_export import ProviderExportPolicy, ProviderExportRecord
from core.ai_provider_export_store import PersistentProviderExportStore
from core.ai_usage_ledger import AIUsageRecord

NOW = datetime.now(UTC)
KEY = "test-command-transport-separate-abcdefghijklmnopqrstuvwxyz"


@pytest.fixture
def example(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'all-attempts.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        for index, provider, outcome, fallback, internal in (
            (1, "vendor-a", "error", False, "0.003"),
            (2, "vendor-b", "success", True, "0.009"),
        ):
            db.add(AIUsageRecord(
                event_id=f"event-{index}", attempt_id=f"physical-{index}",
                tenant_id="tenant-a", unit_id="unit-a", request_id="request-a",
                correlation_id="trace-a", capability="text",
                provider=provider, model=f"model-{index}", route_reason="route",
                fallback_used=fallback, fallback_reason="timeout" if fallback else None,
                input_tokens=12, output_tokens=5, cached_tokens=None,
                latency_ms=50, outcome=outcome, cost_decimal=internal,
                currency="USD", cost_origin="estimated",
                price_snapshot_id="price", event_time=NOW,
            ))
    yield PersistentProviderExportStore(sessions), sessions, engine
    engine.dispose()


def source(index, provider, *, cost=None):
    return ProviderExportRecord(
        provider=provider, model=f"model-{index}",
        tenant_id="tenant-a", unit_id="unit-a",
        request_id="request-a", attempt_id=f"physical-{index}",
        account_ref="fm-account", source_ref=f"provider-{index}",
        observed_at=NOW, usage={"prompt_tokens": 12, "completion_tokens": 5},
        cost_usd=cost,
    )


def import_one(store, index, provider, *, cost):
    admin = VerifiedCommandAdmin(
        user_id="fm-admin", session_id="fm-session",
        token_id=f"unique-import-{index}", issued_at=int(NOW.timestamp()),
        expires_at=int(NOW.timestamp()) + 120,
        step_up_at=int(NOW.timestamp()),
        permissions=frozenset({"core.ai.admin.mutate"}),
    )
    return store.import_snapshot(
        policy=ProviderExportPolicy(
            provider=provider, adapter="openai_compatible",
            account_ref="fm-account",
        ),
        record=source(index, provider, cost=cost),
        principal=admin, now=NOW,
    )


def summary(store):
    return store.reconcile_request(
        tenant_id="tenant-a", unit_id="unit-a", request_id="request-a",
    )


def test_request_reconciles_both_providers_and_fallback_without_zero_cost(example):
    store, sessions, _ = example
    empty = summary(store)
    assert empty["attempts_observed"] == 2
    assert empty["fallback_attempts"] == 1
    assert empty["needs_attention"] is True
    assert all(row["export_status"] == "missing_provider_export" for row in empty["attempts"])
    assert len(empty["per_provider"]) == 2
    assert all(row["reported_unknown_costs"] == 1 for row in empty["per_provider"])
    assert import_one(store, 1, "vendor-a", cost="0.003") == "created"
    assert import_one(store, 2, "vendor-b", cost="0.009") == "created"
    result = summary(store)
    assert result["all_observational_matches"] is False  # failed attempt could be billed
    assert result["needs_attention"] is True
    assert result["attempts"][0]["export_status"] == "needs_attention"
    assert result["attempts"][1]["export_status"] == "observational_match"
    assert [p["provider"] for p in result["per_provider"]] == ["vendor-a", "vendor-b"]
    assert result["per_provider"][0]["reported_known_cost_usd"] == "0.003"
    assert result["per_provider"][1]["internal_known_cost_usd"] == "0.009"
    assert result["per_provider"][1]["fallback_attempts"] == 1
    assert result["provider_invoice_verified"] is False
    assert result["quota_recovery_authorized"] is False
    assert result["real_provider_charges_certified"] is False
    with sessions() as db:
        assert db.get(AIUsageRecord, "event-1").cost_decimal == "0.003"
        assert db.get(AIUsageRecord, "event-2").cost_decimal == "0.009"


def test_request_never_hides_mismatch_unknowns_and_tenant_scope(example):
    store, sessions, _ = example
    import_one(store, 1, "vendor-a", cost="0.300")
    import_one(store, 2, "vendor-b", cost=None)
    current = summary(store)
    assert current["needs_attention"] is True
    assert current["per_provider"][0]["cost_disagreements"] == 1
    assert current["per_provider"][1]["reported_unknown_costs"] == 1
    with pytest.raises(ControlPlaneError, match="request_not_found"):
        store.reconcile_request(tenant_id="foreign", unit_id="unit-a", request_id="request-a")
    with pytest.raises(ControlPlaneError, match="request_scope_invalid"):
        store.reconcile_request(tenant_id="tenant-a", unit_id="unit-a", request_id="")
    with sessions.begin() as db:
        db.add(AIUsageRecord(
            event_id="event-3", attempt_id=None,
            tenant_id="tenant-a", unit_id="unit-a", request_id="request-a",
            correlation_id="trace-a", capability="text",
            provider="vendor-b", model="model-2", route_reason="retry",
            fallback_used=True, fallback_reason="retry", input_tokens=None,
            output_tokens=None, cached_tokens=None, latency_ms=10,
            outcome="unknown", cost_decimal=None, currency="USD",
            cost_origin="unknown", price_snapshot_id="price", event_time=NOW,
        ))
    with pytest.raises(ControlPlaneError, match="attempt_identity_invalid"):
        summary(store)


def test_fm_only_endpoint_rejects_missing_or_forged_identity(example):
    store, _sessions, engine = example
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    app = FastAPI()
    app.state.control_plane_engine = engine
    app.include_router(finops_alert_policy_router(
        trust=CommandTrustPolicy(
            issuer="fm-command", audience="fm-core-recovery",
            public_key_pem=pub,
        ),
        transport_key=KEY,
    ))
    now = int(datetime.now(UTC).timestamp())
    token = jwt.encode({
        "iss": "fm-command", "aud": "fm-core-recovery",
        "sub": "fm-admin", "jti": "request-read-jti",
        "session_id": "session", "iat": now, "nbf": now,
        "exp": now + 120, "step_up_at": now,
        "actor_type": "human", "role": "platform_admin",
        "scope": "fm_core_platform", "permissions": ["core.ai.admin.mutate"],
    }, private, algorithm="RS256")
    http = TestClient(app)
    path = "/internal/v1/command/ai/finops/provider-export/request-reconciliation"
    body = {"tenant_id": "tenant-a", "unit_id": "unit-a", "request_id": "request-a"}
    headers = {"Authorization": "Bearer " + token, "X-FM-Recovery-Service-Key": KEY}
    assert http.post(path, json=body).status_code == 401
    assert http.post(path, json=body, headers={
        "Authorization": headers["Authorization"],
    }).status_code == 401
    assert http.post(path, json=body, headers={
        **headers, "X-FM-Recovery-Service-Key": "invalid",
    }).status_code == 401
    assert http.post(path, json={**body, "unexpected": 1}, headers=headers).status_code == 422
    assert http.post(path, json={**body, "tenant_id": "other"}, headers=headers).status_code == 409
    result = http.post(path, json=body, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["needs_attention"] is True
    assert result.json()["attempts_observed"] == 2
    assert result.json()["provider_invoice_verified"] is False
