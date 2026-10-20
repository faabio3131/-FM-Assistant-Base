"""Mocked Evolution v2 read-only evidence lookup. Never sends a message."""
from __future__ import annotations

import httpx
import pytest

from fm_assistant.channels.whatsapp_evolution import (
    EvolutionClient, EvolutionSettings, EvolutionUnavailable,
)


def test_evidence_lookup_scopes_reference_and_uses_instance_token():
    requests = []

    def provider(req):
        requests.append(req)
        assert req.headers["apikey"] == "instance-" + "x" * 32
        assert req.url.path == "/chat/findMessages/fm_" + "a" * 32
        assert req.method == "POST"
        assert req.read() == b'{"where":{"key":{"id":"OUTBOUND-1"}}}'
        return httpx.Response(200, json={"messages": {
            "records": [{"key": {"id": "OUTBOUND-1", "fromMe": True},
                         "message": {"conversation": "Do not log"}},
                        {"key": {"id": "OTHER", "fromMe": True}}],
        }})

    client = EvolutionClient(
        EvolutionSettings(
            origin="https://evolution.example.test",
            global_key="global-" + "y" * 32,
        ),
        client=httpx.Client(transport=httpx.MockTransport(provider)),
    )
    digest = client.find_outbound_evidence(
        "fm_" + "a" * 32,
        instance_token="instance-" + "x" * 32,
        provider_reference="OUTBOUND-1",
    )
    assert digest is not None and len(digest) == 64
    assert len(requests) == 1


def test_evidence_lookup_rejects_inbound_and_missing_provider_records():
    def provider(_req):
        return httpx.Response(200, json={"messages": {
            "records": [{"key": {"id": "OUTBOUND-1", "fromMe": False}}],
        }})
    client = EvolutionClient(
        EvolutionSettings(
            origin="https://evolution.example.test",
            global_key="global-" + "y" * 32,
        ),
        client=httpx.Client(transport=httpx.MockTransport(provider)),
    )
    assert client.find_outbound_evidence(
        "fm_" + "a" * 32, instance_token="instance-" + "x" * 32,
        provider_reference="OUTBOUND-1",
    ) is None
    with pytest.raises(ValueError):
        client.find_outbound_evidence(
            "fm_" + "a" * 32, instance_token="instance-" + "x" * 32,
            provider_reference="../../secrets",
        )
    with pytest.raises(EvolutionUnavailable):
        failing = EvolutionClient(
            EvolutionSettings(
                origin="https://evolution.example.test",
                global_key="global-" + "y" * 32,
            ),
            client=httpx.Client(transport=httpx.MockTransport(
                lambda _: httpx.Response(503),
            )),
        )
        failing.find_outbound_evidence(
            "fm_" + "a" * 32, instance_token="instance-" + "x" * 32,
            provider_reference="OUTBOUND-1",
        )
