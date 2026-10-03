from __future__ import annotations

import hashlib
import hmac

from fm_assistant.channels.whatsapp_meta import MetaWhatsAppClient


APP_SECRET = "app-secret-test"
VERIFY_TOKEN = "verify-token-test"


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _setup_channel(client, provision_credential, *, tenant="tenant-wa", unit="unit-wa"):
    api_key = provision_credential(client, tenant, unit)
    persona = client.put(
        "/v1/persona",
        headers=_headers(api_key),
        json={
            "public_name": "Nina",
            "language": "pt-BR",
            "tone": "consultivo",
            "instructions": "",
            "enabled": True,
        },
    )
    assert persona.status_code == 200
    configured = client.put(
        "/v1/channels/whatsapp",
        headers=_headers(api_key),
        json={
            "phone_number_id": "phone-123",
            "business_account_id": "waba-123",
            "access_token": "token-secret",
            "app_secret": APP_SECRET,
            "verify_token": VERIFY_TOKEN,
            "graph_api_version": "v23.0",
        },
    )
    assert configured.status_code == 200, configured.text
    return api_key, configured.json()["channel_id"]


def _text_payload(message_id: str = "wamid-1") -> bytes:
    return (
        '{"object":"whatsapp_business_account","entry":[{"id":"waba-123",'
        '"changes":[{"field":"messages","value":{"messages":[{'
        f'"from":"5511999999999","id":"{message_id}","timestamp":"1",'
        '"type":"text","text":{"body":"Oi"}}]}}]}]}'
    ).encode()


def _audio_payload(message_id: str = "wamid-audio") -> bytes:
    return (
        '{"object":"whatsapp_business_account","entry":[{"id":"waba-123",'
        '"changes":[{"field":"messages","value":{"messages":[{'
        f'"from":"5511999999999","id":"{message_id}","timestamp":"1",'
        '"type":"audio","audio":{"id":"media-1","mime_type":"audio/ogg"}}]}}]}]}'
    ).encode()


def _signature(body: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()


class _MetaResponse:
    status_code = 200

    def json(self):
        return {"messages": [{"id": "wamid-out-1"}]}


def test_whatsapp_challenge_and_tenant_isolation(client, provision_credential):
    key_a, channel_id = _setup_channel(client, provision_credential)
    key_b = provision_credential(client, "tenant-b", "unit-b")

    challenge = client.get(
        f"/webhooks/meta/whatsapp/{channel_id}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "challenge-123",
        },
    )
    assert challenge.status_code == 200
    assert challenge.text == "challenge-123"

    foreign = client.get("/v1/channels/whatsapp", headers=_headers(key_b))
    assert foreign.status_code == 404

    own = client.get("/v1/channels/whatsapp", headers=_headers(key_a))
    assert own.status_code == 200
    assert own.json()["channel_id"] == channel_id
    assert "access_token" not in own.json()
    assert "app_secret" not in own.json()


def test_invalid_signature_fails_closed(client, provision_credential):
    _key, channel_id = _setup_channel(client, provision_credential)
    response = client.post(
        f"/webhooks/meta/whatsapp/{channel_id}",
        content=_text_payload(),
        headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
    )
    assert response.status_code == 401


def test_text_webhook_is_idempotent(client, provision_credential, monkeypatch):
    _key, channel_id = _setup_channel(client, provision_credential)
    calls: list[dict] = []

    def fake_post(url, *, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _MetaResponse()

    monkeypatch.setattr(
        "fm_assistant.channels.whatsapp_meta.httpx.post",
        fake_post,
    )

    body = _text_payload()
    first = client.post(
        f"/webhooks/meta/whatsapp/{channel_id}",
        content=body,
        headers={"X-Hub-Signature-256": _signature(body)},
    )
    second = client.post(
        f"/webhooks/meta/whatsapp/{channel_id}",
        content=body,
        headers={"X-Hub-Signature-256": _signature(body)},
    )

    assert first.status_code == 204
    assert second.status_code == 204
    assert len(calls) == 1
    assert calls[0]["json"]["to"] == "5511999999999"
    assert calls[0]["json"]["type"] == "text"


def test_audio_without_transcriber_enters_safe_handoff(
    client,
    provision_credential,
    monkeypatch,
):
    _key, channel_id = _setup_channel(client, provision_credential)
    sent: list[str] = []

    monkeypatch.setattr(
        MetaWhatsAppClient,
        "download_audio",
        lambda self, **kwargs: (b"audio-bytes", "audio/ogg"),
    )

    def fake_post(url, *, headers, json, timeout):
        del url, headers, timeout
        sent.append(json["text"]["body"])
        return _MetaResponse()

    monkeypatch.setattr(
        "fm_assistant.channels.whatsapp_meta.httpx.post",
        fake_post,
    )

    body = _audio_payload()
    response = client.post(
        f"/webhooks/meta/whatsapp/{channel_id}",
        content=body,
        headers={"X-Hub-Signature-256": _signature(body)},
    )

    assert response.status_code == 204
    assert len(sent) == 1
    assert "atendimento humano" in sent[0]
