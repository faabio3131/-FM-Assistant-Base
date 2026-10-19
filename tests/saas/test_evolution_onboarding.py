"""Synthetic QR onboarding; no VPS, WhatsApp account or real credentials."""
from __future__ import annotations

import base64

import httpx
import pytest

from fm_assistant.channels.whatsapp_evolution import (
    EvolutionClient,
    EvolutionSettings,
    EvolutionUnavailable,
)
from fm_assistant.evolution_onboarding import EvolutionOnboarding


def _headers(key):
    return {"Authorization": f"Bearer {key}"}


def _transport(on_request):
    client = httpx.Client(transport=httpx.MockTransport(on_request))
    return EvolutionClient(
        EvolutionSettings(
            origin="https://evolution.example.test",
            global_key="synthetic-fm-admin-key-" + "x" * 32,
        ),
        client=client,
    )


def test_https_and_separate_global_key_required():
    assert "x" * 40 not in repr(EvolutionSettings(
        origin="https://evolution.example.test", global_key="x" * 40,
    ))
    for origin in (
        "http://evolution.example.test", "https://localhost",
        "https://user:pass@evolution.example.test",
        "https://evolution.example.test/admin",
        "https://evolution.example.test:8080",
    ):
        with pytest.raises(ValueError, match="evolution_settings_invalid"):
            EvolutionSettings(origin=origin, global_key="x" * 40)


def test_qr_adapter_never_sends_master_key_in_body():
    qr = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * 128).decode()
    seen = []

    def handler(request):
        assert request.headers["apikey"].startswith("synthetic-fm-admin-key-")
        assert request.url.host == "evolution.example.test"
        assert "synthetic-fm-admin-key" not in request.content.decode()
        seen.append(request.url.path)
        if request.url.path == "/instance/create":
            return httpx.Response(201, json={"hash": {"token": "individual-token"}})
        return httpx.Response(200, json={"base64": "data:image/png;base64," + qr})

    adapter = _transport(handler)
    assert adapter.create("fm_" + "f" * 32) == "individual-token"
    assert adapter.connect("fm_" + "f" * 32) == "data:image/png;base64," + qr
    assert seen == [
        "/instance/create", "/instance/connect/fm_" + "f" * 32,
    ]


def test_bad_qr_and_ambiguous_remote_failure_fail_closed():
    def bad_qr(_):
        return httpx.Response(200, json={"base64": "not-valid-base64"})

    with pytest.raises(EvolutionUnavailable, match="evolution_qr_invalid"):
        _transport(bad_qr).connect("fm_" + "f" * 32)
    with pytest.raises(EvolutionUnavailable, match="evolution_gateway_unavailable"):
        _transport(lambda _: httpx.Response(503)).create("fm_" + "f" * 32)


def test_tenant_scoped_api_provision_and_qr(client, provision_credential):
    key_a = provision_credential(client, "tenant-a", "unit-a")
    key_b = provision_credential(client, "tenant-b", "unit-b")
    assert client.post("/v1/channels/whatsapp/qr/provision").status_code == 401
    assert client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_headers(key_a),
    ).status_code == 503

    qr = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * 128).decode()

    def handler(request):
        if request.url.path == "/instance/create":
            return httpx.Response(201, json={"hash": {"token": "test-token-secret"}})
        return httpx.Response(200, json={"base64": qr})

    original = client.app.state.integration_repository
    from fm_assistant.credential_vault import FernetCredentialVault

    client.app.state.evolution_onboarding = EvolutionOnboarding(
        repository=original,
        vault=FernetCredentialVault(client.app.state.settings.channel_encryption_key),
        transport=_transport(handler),
    )
    created = client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_headers(key_a),
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["provider_key"] == "whatsapp_evolution"
    assert payload["status"] == "draft"
    assert "test-token-secret" not in created.text
    cid = payload["connection_id"]
    from sqlalchemy import create_engine, text

    engine = create_engine(client.app.state.settings.database_url)
    with engine.connect() as db:
        row = db.execute(text(
            "SELECT ciphertext FROM assistant_integration_secret_versions "
            "WHERE connection_id = :id AND secret_name = :name"
        ), {"id": cid, "name": "instance_token"}).scalar_one()
        assert row != "test-token-secret"
        assert "test-token-secret" not in row
    engine.dispose()

    other = client.get(
        f"/v1/channels/whatsapp/qr/{cid}", headers=_headers(key_b),
    )
    assert other.status_code == 404
    result = client.get(
        f"/v1/channels/whatsapp/qr/{cid}", headers=_headers(key_a),
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "connecting"
    assert result.json()["qr_data_url"].startswith("data:image/png;base64,")
    assert result.headers["cache-control"] == "no-store"
    repeat = client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_headers(key_a),
    )
    assert repeat.status_code == 409
    forbidden_config_change = client.put(
        f"/v1/integrations/{cid}/config", headers=_headers(key_a),
        json={"config": {"instance_name": "attacker-supplied"}},
    )
    assert forbidden_config_change.status_code == 409
    invalid_generic = client.post(
        "/v1/integrations", headers=_headers(key_a),
        json={
            "provider_key": "whatsapp_evolution",
            "config": {"instance_name": "arbitrary"},
            "secrets": {"instance_token": "tenant-controlled"},
        },
    )
    assert invalid_generic.status_code == 400


def test_remote_ambiguous_create_never_retries_or_exposes_secret(
    client, provision_credential,
):
    key = provision_credential(client, "tenant-uncertain", "unit-a")
    attempts = []

    def handler(request):
        attempts.append(request.url.path)
        return httpx.Response(503, json={"secret": "should-never-echo"})

    from fm_assistant.credential_vault import FernetCredentialVault

    client.app.state.evolution_onboarding = EvolutionOnboarding(
        repository=client.app.state.integration_repository,
        vault=FernetCredentialVault(client.app.state.settings.channel_encryption_key),
        transport=_transport(handler),
    )
    first = client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_headers(key),
    )
    assert first.status_code == 409
    assert "should-never-echo" not in first.text
    again = client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_headers(key),
    )
    assert again.status_code == 409
    assert attempts == ["/instance/create"]


def test_catalog_registers_qr_provider_without_requiring_user_tokens(
    client, provision_credential,
):
    key = provision_credential(client, "tenant-a", "unit-a")
    result = client.get("/v1/integrations/catalog", headers=_headers(key))
    assert result.status_code == 200
    entry = next(
        x for x in result.json()
        if x["provider_key"] == "whatsapp_evolution"
    )
    assert "whatsapp.qr" in entry["capabilities"]
    assert entry["integration_type"] == "whatsapp"


def test_qr_panel_is_human_session_only_and_has_strict_csp(client, provision_credential):
    key = provision_credential(client, "tenant-a", "unit-a")
    assert client.get("/v1/channels/whatsapp/qr/panel").status_code == 401
    # Machine credentials are not equivalent to an owner session.
    assert client.get(
        "/v1/channels/whatsapp/qr/panel", headers=_headers(key),
    ).status_code == 401
    from test_identity_rbac import _bootstrap, _login

    _bootstrap(client, tenant_id="tenant-owner-qr", unit_id="unit-owner-qr",
               email="qr-owner@example.com")
    _login(client, tenant_id="tenant-owner-qr", email="qr-owner@example.com")
    html = client.get("/v1/channels/whatsapp/qr/panel")
    assert html.status_code == 200, html.text
    assert "Conecte seu WhatsApp" in html.text
    assert "script-src 'nonce-" in html.headers["content-security-policy"]
    assert html.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in html.headers["content-security-policy"]
    # A customer can access their panel even before the FM transport is activated,
    # while API calls remain explicitly unavailable instead of using fake QR codes.
    assert client.get("/v1/channels/whatsapp/qr/current").status_code == 503


def test_qr_current_is_scoped_and_never_returns_secrets(
    client, provision_credential,
):
    api_key = provision_credential(client, "tenant-read-qr", "unit-read-qr")
    assert client.get(
        "/v1/channels/whatsapp/qr/current", headers=_headers(api_key),
    ).status_code == 503


def test_instance_outbound_uses_individual_token_not_fm_master_key():
    requests = []

    def send(request):
        requests.append(request)
        assert request.headers["apikey"] == "synthetic-instance-token-value"
        assert request.headers["apikey"] != "synthetic-fm-admin-key-" + "x" * 32
        assert request.url.path == "/message/sendText/fm_" + "f" * 32
        assert request.content == b'{"number":"5511999999999","text":"Resposta segura"}'
        return httpx.Response(200, json={"key": {"id": "WA-OUT-1"}})

    sender = _transport(send)
    assert sender.send_text(
        "fm_" + "f" * 32, instance_token="synthetic-instance-token-value",
        recipient="5511999999999", message="Resposta segura",
    ) == "WA-OUT-1"
    assert len(requests) == 1


def test_outbound_network_ambiguity_is_never_a_success():
    sender = _transport(lambda _: httpx.Response(503))
    with pytest.raises(EvolutionUnavailable, match="gateway_unavailable"):
        sender.send_text(
            "fm_" + "f" * 32, instance_token="synthetic-instance-token-value",
            recipient="5511999999999", message="Resposta segura",
        )
    with pytest.raises(ValueError, match="outbound_invalid"):
        sender.send_text(
            "fm_" + "f" * 32, instance_token="synthetic-instance-token-value",
            recipient="123", message="Resposta segura",
        )
