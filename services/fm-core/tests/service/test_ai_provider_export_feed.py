"""Configured provider feeds: no arbitrary destinations or invented evidence."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from core.ai_control_plane import ControlPlaneError
from core.ai_provider_export_feed import (
    ProviderFeedConfig,
    configured_feed,
    fetch_observations,
)


def config(**overrides):
    args = {
        "provider": "provider-a",
        "account_ref": "fm-account",
        "adapter": "openai_compatible",
        "url": "https://reports.vendor-example.com/v1/usage/attempt",
        "host": "reports.vendor-example.com",
        "token": "secret-account-api-token-for-export-connector-2026",
    }
    args.update(overrides)
    return ProviderFeedConfig(**args)


def attempt():
    return [{"request_id": "req-1", "attempt_id": "attempt-1", "model": "model-1"}]


def observation():
    return {
        "tenant_id": "tenant-fm", "unit_id": "unit-1", "provider": "provider-a",
        "account_ref": "fm-account", "request_id": "req-1",
        "attempt_id": "attempt-1", "model": "model-1",
        "source_ref": "external-report-1",
        "observed_at": datetime.now(UTC).isoformat(),
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
        "cost_usd": "0.004",
    }


def test_normalized_report_fetches_exact_physical_attempt_and_no_prompt_data():
    expected = observation()

    def exchange(request):
        assert request.method == "POST"
        assert str(request.url) == "https://reports.vendor-example.com/v1/usage/attempt"
        assert request.headers["Authorization"].startswith("Bearer secret-")
        body = json.loads(request.content)
        assert set(body) == {
            "schema", "tenant_id", "unit_id", "provider", "account_ref", "attempts",
        }
        assert body["attempts"] == attempt()
        assert "prompt" not in str(body)
        return httpx.Response(200, json={
            "schema": "fm.provider.export-read.v1", "records": [expected],
        })

    policy, records = fetch_observations(
        config=config(), tenant_id="tenant-fm", unit_id="unit-1",
        attempts=attempt(), transport=httpx.MockTransport(exchange),
    )
    assert policy.provider == "provider-a"
    assert len(records) == 1
    assert records[0].attempt_id == "attempt-1"
    assert records[0].cost_usd == "0.004"


@pytest.mark.parametrize("mutation", [
    {"tenant_id": "foreign-tenant"},
    {"unit_id": "another-unit"},
    {"provider": "another-vendor"},
    {"account_ref": "foreign-account"},
    {"request_id": "unknown-request"},
    {"attempt_id": "unknown-attempt"},
    {"model": "wrong-model"},
])
def test_foreign_or_unrequested_provider_records_are_never_accepted(mutation):
    record = {**observation(), **mutation}

    def exchange(_request):
        return httpx.Response(200, json={
            "schema": "fm.provider.export-read.v1", "records": [record],
        })
    with pytest.raises(ControlPlaneError, match="scope_invalid"):
        fetch_observations(
            config=config(), tenant_id="tenant-fm", unit_id="unit-1",
            attempts=attempt(), transport=httpx.MockTransport(exchange),
        )


def test_empty_provider_report_is_explicitly_unknown_not_a_zero_cost():
    policy, records = fetch_observations(
        config=config(), tenant_id="tenant-fm", unit_id="unit-1",
        attempts=attempt(), transport=httpx.MockTransport(
            lambda _req: httpx.Response(200, json={
                "schema": "fm.provider.export-read.v1", "records": [],
            })
        ),
    )
    assert records == ()
    assert policy.account_ref == "fm-account"


@pytest.mark.parametrize("unsafe_url", [
    "http://reports.vendor-example.com/v1/usage",
    "https://127.0.0.1/v1/usage",
    "https://reports.vendor-example.com@evil.example/v1/usage",
    "https://reports.vendor-example.com/v1/usage?q=secret",
    "https://reports.vendor-example.com:8443/v1/usage",
    "https://localhost/v1/usage",
])
def test_connection_is_pinned_to_configured_public_https_host(unsafe_url):
    with pytest.raises(ControlPlaneError):
        config(url=unsafe_url)


def test_remote_redirect_and_oversized_responses_fail_closed():
    for response in (
        httpx.Response(302, headers={"location": "http://127.0.0.1"}),
        httpx.Response(200, content=b"x" * (512 * 1024 + 1)),
    ):
        with pytest.raises(ControlPlaneError):
            fetch_observations(
                config=config(), tenant_id="tenant-fm", unit_id="unit-1",
                attempts=attempt(),
                transport=httpx.MockTransport(lambda _req, saved=response: saved),
            )


def test_configuration_is_fm_owned_and_credentials_never_in_repr():
    payload = json.dumps([{
        "provider": "provider-a", "account_ref": "fm-account",
        "adapter": "openai_compatible",
        "url": "https://reports.vendor-example.com/v1/usage/attempt",
        "host": "reports.vendor-example.com",
        "token": "secret-account-api-token-for-export-connector-2026",
    }])
    selected = configured_feed("provider-a", "fm-account", raw=payload)
    assert "secret-account" not in repr(selected)
    with pytest.raises(ControlPlaneError, match="feed_not_configured"):
        configured_feed("provider-other", "fm-account", raw=payload)
    with pytest.raises(ControlPlaneError, match="feed_duplicate_source"):
        configured_feed("provider-a", "fm-account", raw=json.dumps(
            [json.loads(payload)[0], json.loads(payload)[0]]
        ))


def test_duplicate_readback_physical_attempt_ids_are_rejected():
    with pytest.raises(ControlPlaneError, match="duplicate_request"):
        fetch_observations(
            config=config(), tenant_id="tenant-fm", unit_id="unit-1",
            attempts=attempt() * 2, transport=httpx.MockTransport(
                lambda _req: httpx.Response(200, json={})
            ),
        )
