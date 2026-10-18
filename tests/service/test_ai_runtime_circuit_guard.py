"""F3.8 guarded provider routing; all provider calls synthetic."""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from core.ai_circuit_breaker import CircuitPolicy
from core.ai_circuit_state_store import PersistentCircuit, ProviderCircuitRecord
from core.ai_control_plane_runtime import CoreControlPlaneAIRuntime
from core.ai_router import FalhaRotaDefinitiva, FalhaRotaTransitoria
from core.ai_service_contracts import TextMessage
from tests.service.test_ai_control_plane_runtime import Resolver, _plane, _policy

NOW = datetime(2026, 10, 18, tzinfo=UTC)


def _call(runtime, request_id="req-one"):
    return runtime.generate_text(
        tenant_id="tenant-a", unit_id="unit-1",
        request_id=request_id, correlation_id="corr",
        system_prompt="test", messages=(TextMessage(role="user", content="hi"),),
    )


def _guarded_store(tenant_managed=False, configured=True):
    store = _plane()
    if tenant_managed:
        store.add_route(_policy(
            identifier="byok", scope="tenant", tenant="tenant-a",
            credential_source="tenant_managed",
        ))
    else:
        store.add_route(_policy(identifier="platform", scope="platform"))
    if configured:
        with store._sessions.begin() as db:
            db.add(ProviderCircuitRecord(
                provider_id="openai", phase="closed", failures=0,
                until=None, probe_id=None, version=1,
            ))
    return store, PersistentCircuit(
        store._sessions, CircuitPolicy(
            threshold=1, cooldown_seconds=30, probe_seconds=5,
        ),
    )


def test_transient_provider_outage_opens_circuit_and_blocks_next_call(monkeypatch):
    store, circuit = _guarded_store()
    calls = []

    def timeout(url, **kwargs):
        calls.append(1)
        raise httpx.TimeoutException("synthetic-provider-timeout")

    monkeypatch.setattr("core.ai_providers.httpx.post", timeout)
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=Resolver(), circuit=circuit,
    )
    with pytest.raises(FalhaRotaTransitoria):
        _call(runtime)
    with pytest.raises(FalhaRotaDefinitiva, match="core_circuit.unavailable"):
        _call(runtime, request_id="second")
    assert len(calls) == 1
    with store._sessions() as db:
        row = db.get(ProviderCircuitRecord, "openai")
        assert row.phase == "open"
        assert row.failures == 1


def test_unconfigured_persistent_circuit_denies_provider_execution(monkeypatch):
    store, circuit = _guarded_store(configured=False)
    calls = []
    monkeypatch.setattr("core.ai_providers.httpx.post", lambda *a, **k: calls.append(1))
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=Resolver(), circuit=circuit,
    )
    with pytest.raises(FalhaRotaDefinitiva, match="core_circuit.unavailable"):
        _call(runtime)
    assert not calls


def test_byok_circuit_denies_until_tenant_partition_is_proven(monkeypatch):
    store, circuit = _guarded_store(tenant_managed=True)
    calls = []
    monkeypatch.setattr("core.ai_providers.httpx.post", lambda *a, **k: calls.append(1))
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=Resolver(), circuit=circuit,
    )
    with pytest.raises(FalhaRotaDefinitiva, match="byok_partition_required"):
        _call(runtime)
    assert not calls


def test_successful_provider_call_keeps_circuit_closed(monkeypatch):
    store, circuit = _guarded_store()
    calls = []

    def ok(url, **kwargs):
        calls.append(1)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", ok)
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=Resolver(), circuit=circuit,
    )
    assert _call(runtime).content == "ok"
    assert len(calls) == 1
    with store._sessions() as db:
        row = db.get(ProviderCircuitRecord, "openai")
        assert row.phase == "closed"
