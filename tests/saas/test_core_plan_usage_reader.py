"""Synthetic end-to-end contract for Core -> Assistant quota visibility."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from fm_assistant.core_plan_usage_reader import CoreQuotaUsageHTTPReader


def _response(*, now: datetime, **overrides):
    result = {
        "tenant_id": "tenant-a", "unit_id": "unit-a",
        "resource": "ai.total_tokens", "scope": "tenant",
        "policy_revision": 3, "limit_units": 1000, "window_seconds": 86400,
        "consumed_units": 300, "reserved_units": 200,
        "remaining_units": 500, "observed_at": now.isoformat(),
    }
    result.update(overrides)
    return httpx.Response(200, json=result, request=httpx.Request(
        "GET", "https://core.invalid/v1/plan/usage",
    ))


def _read(reader, now):
    return reader.read(
        tenant_id="tenant-a", unit_id="unit-a",
        metric="ai.total_tokens", scope="tenant", at=now,
        policy_revision=3, limit_units=1000, window_seconds=86400,
    )


def _stub_core_http(monkeypatch, handler):
    """Exercise the real client construction boundary with synthetic I/O."""
    settings = []

    class StubClient:
        def __init__(self, **kwargs):
            settings.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            return handler(url, **kwargs)

    monkeypatch.setattr("fm_assistant.core_plan_usage_reader.httpx.Client", StubClient)
    return settings


def test_reader_uses_trusted_service_key_and_exact_customer_scope(monkeypatch):
    now = datetime.now(UTC)
    sent = []

    def mock_get(url, **kwargs):
        sent.append((url, kwargs))
        return _response(now=now)

    settings = _stub_core_http(monkeypatch, mock_get)
    reader = CoreQuotaUsageHTTPReader(
        core_origin="https://core.invalid", service_key="synthetic-secret",
    )
    actual = _read(reader, now)
    assert actual is not None
    assert (actual.consumed_units, actual.reserved_units, actual.remaining_units) == (
        300, 200, 500,
    )
    assert sent[0][1]["headers"]["X-Core-Service-Key"] == "synthetic-secret"
    assert sent[0][1]["params"]["tenant_id"] == "tenant-a"
    assert settings[0]["follow_redirects"] is False
    assert settings[0]["trust_env"] is False
    assert settings[0]["timeout"] == 3.0


@pytest.mark.parametrize("changed", [
    {"tenant_id": "tenant-b"}, {"unit_id": "unit-b"},
    {"policy_revision": 2}, {"window_seconds": 3600},
    {"limit_units": 2000}, {"remaining_units": -1},
    {"consumed_units": "300"}, {"observed_at": "unknown"},
])
def test_reader_rejects_mismatch_instead_of_inventing_remaining(monkeypatch, changed):
    now = datetime.now(UTC)
    _stub_core_http(
        monkeypatch, lambda url, **kw: _response(now=now, **changed),
    )
    reader = CoreQuotaUsageHTTPReader(
        core_origin="https://core.invalid", service_key="synthetic",
    )
    assert _read(reader, now) is None


def test_reader_rejects_stale_and_failed_provider_without_false_balance(monkeypatch):
    now = datetime.now(UTC)
    _stub_core_http(
        monkeypatch, lambda url, **kw: _response(now=now - timedelta(minutes=10)),
    )
    reader = CoreQuotaUsageHTTPReader(
        core_origin="https://core.invalid", service_key="synthetic",
    )
    assert _read(reader, now) is None

    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("synthetic network timeout")

    _stub_core_http(monkeypatch, timeout)
    assert _read(reader, now) is None


def test_reader_disallows_plaintext_or_embedded_credentials():
    for origin in (
        "http://core.invalid", "https://name:password@core.invalid",
        "https://core.invalid/malicious",
        "https://core.invalid?tenant=other",
    ):
        with pytest.raises(ValueError, match="plan.core_transport_untrusted"):
            CoreQuotaUsageHTTPReader(core_origin=origin, service_key="synthetic")
