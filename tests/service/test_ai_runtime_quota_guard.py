"""F3.8 opt-in quota guards are executed before the first provider call."""
from __future__ import annotations

import httpx
import pytest

from core.ai_control_plane_runtime import CoreControlPlaneAIRuntime
from core.ai_quota_store import (
    AIQuotaPolicyRecord, AIQuotaReservationRecord, QuotaDenied, QuotaReservations,
    ReservationState,
)
from core.ai_router import CapabilityIA
from core.ai_service_contracts import TextMessage
from core.seguranca.segredos import SecretValue
from tests.service.test_ai_control_plane_runtime import _plane, _policy


class SyntheticCredentials:
    def resolve(self, *, tenant_id, credential_source, secret_reference):
        return SecretValue("synthetic-provider-key")


def _request(runtime, tenant="tenant-a", request_id="same-request"):
    return runtime.generate_text(
        tenant_id=tenant, unit_id="unit-1",
        request_id=request_id, correlation_id="synthetic-correlation",
        system_prompt="synthetic", messages=(TextMessage(role="user", content="hi"),),
    )


def _runtime():
    store = _plane()
    store.add_route(_policy(identifier="platform", scope="platform"))
    with store._sessions.begin() as db:
        db.add(AIQuotaPolicyRecord(
            tenant_id="tenant-a", unit_id="unit-1",
            capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO.value,
            limit_units=1, window_seconds=60, revision=1,
        ))
    return CoreControlPlaneAIRuntime(
        control_plane=store, credentials=SyntheticCredentials(),
        quota=QuotaReservations(store._sessions),
    ), store._sessions


def test_unauthorized_tenant_never_reaches_provider(monkeypatch):
    runtime, _ = _runtime()
    calls = []
    monkeypatch.setattr("core.ai_providers.httpx.post", lambda *a, **kw: calls.append(1))
    with pytest.raises(QuotaDenied, match="policy_unavailable"):
        _request(runtime, tenant="tenant-b")
    assert calls == []


def test_first_success_settles_one_unit_and_replay_denied_before_provider(monkeypatch):
    runtime, sessions = _runtime()
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", fake_post)
    assert _request(runtime).content == "ok"
    with pytest.raises(QuotaDenied, match="execution_replay_denied"):
        _request(runtime)
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        _request(runtime, request_id="other")
    assert len(calls) == 1
    with sessions() as db:
        record = db.get(
            AIQuotaReservationRecord, (
                "tenant-a", "unit-1",
                CapabilityIA.ATENDIMENTO_INTERPRETACAO.value, "same-request",
            ),
        )
        assert record.state == ReservationState.SETTLED
        assert record.consumed_units == 1


def test_provider_timeout_keeps_reservation_for_manual_reconciliation(monkeypatch):
    runtime, sessions = _runtime()
    calls = []

    def fake_post(url, **kwargs):
        calls.append(1)
        raise httpx.TimeoutException("synthetic-provider-timeout")

    monkeypatch.setattr("core.ai_providers.httpx.post", fake_post)
    with pytest.raises(Exception):
        _request(runtime)
    with pytest.raises(QuotaDenied, match="execution_replay_denied"):
        _request(runtime)
    assert len(calls) == 1
    with sessions() as db:
        record = db.get(
            AIQuotaReservationRecord, (
                "tenant-a", "unit-1",
                CapabilityIA.ATENDIMENTO_INTERPRETACAO.value, "same-request",
            ),
        )
        assert record.state == ReservationState.RESERVED
        assert record.consumed_units == 0
