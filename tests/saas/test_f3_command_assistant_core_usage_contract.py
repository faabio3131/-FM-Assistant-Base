"""Internal Command→Assistant→Core contract simulation (no external homologation).

Core retains quota authority; tenant-facing dashboard cannot infer usage from an
AI text response or FM provider expenditure.
"""
from datetime import UTC, datetime

import httpx

from fm_assistant.core_client import CoreAIClient
from fm_assistant.core_plan_usage_reader import CoreQuotaUsageHTTPReader
from fm_assistant.provider_usage_reconciliation import from_trusted_core_receipt


def test_core_generation_and_authoritative_metering_remain_separate(monkeypatch):
    def post(url, *, headers, json, timeout):
        assert url == "https://core.internal.test/v1/ai/text"
        assert headers["X-Core-Service-Key"] == "synthetic-internal-key"
        assert json["tenant_id"] == "tenant-one"
        assert json["unit_id"] == "unit-one"
        assert json["correlation_id"] == "message-one"
        return httpx.Response(200, json={"content": "Resposta segura"})

    def get(url, *, params, headers, timeout, follow_redirects):
        assert url == "https://core.internal.test/v1/plan/usage"
        assert headers["X-Core-Service-Key"] == "synthetic-internal-key"
        assert params["tenant_id"] == "tenant-one"
        assert params["unit_id"] == "unit-one"
        assert not follow_redirects
        return httpx.Response(200, json={
            **params, "policy_revision": 4,
            "limit_units": 2000, "window_seconds": 3600,
            "consumed_units": 100, "reserved_units": 200,
            "remaining_units": 1700, "observed_at": datetime.now(UTC).isoformat(),
        })

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    client = CoreAIClient(
        base_url="https://core.internal.test", service_key="synthetic-internal-key",
    )
    assert client.generate_text(
        tenant_id="tenant-one", unit_id="unit-one",
        system_prompt="safe", messages=[{"role": "user", "content": "Oi"}],
        correlation_id="message-one",
    ) == "Resposta segura"
    reading = CoreQuotaUsageHTTPReader(
        core_origin="https://core.internal.test",
        service_key="synthetic-internal-key",
    ).read(
        tenant_id="tenant-one", unit_id="unit-one",
        metric="ai.total_tokens", scope="tenant", at=datetime.now(UTC),
        policy_revision=4, limit_units=2000, window_seconds=3600,
    )
    assert reading is not None
    assert reading.consumed_units == 100
    assert reading.reserved_units == 200
    unknown = from_trusted_core_receipt({
        "provider": "gemini", "model": "gemini-model",
        "request_id": "message-one", "usage_status": "uncertain",
    }, request_id="message-one")
    assert unknown.total_tokens is None
    assert unknown.cost_usd is None


def test_broken_core_metering_does_not_advertise_available_credits(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: httpx.Response(
        200, json={
            "tenant_id": "other-tenant", "unit_id": "unit-one",
            "resource": "ai.total_tokens", "scope": "tenant",
            "policy_revision": 4, "limit_units": 2000,
            "window_seconds": 3600, "consumed_units": 0,
            "reserved_units": 0, "remaining_units": 2000,
            "observed_at": datetime.now(UTC).isoformat(),
        },
    ))
    reading = CoreQuotaUsageHTTPReader(
        core_origin="https://core.internal.test", service_key="synthetic-key",
    ).read(
        tenant_id="tenant-one", unit_id="unit-one",
        metric="ai.total_tokens", scope="tenant", at=datetime.now(UTC),
        policy_revision=4, limit_units=2000, window_seconds=3600,
    )
    assert reading is None
