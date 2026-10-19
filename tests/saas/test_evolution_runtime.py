"""Synthetic signed webhook -> Assistant conversation -> per-instance WhatsApp outbound."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx

from fm_assistant.channels.evolution_events import EvolutionEventVerifier
from fm_assistant.channels.whatsapp_evolution import EvolutionClient, EvolutionSettings
from fm_assistant.credential_vault import FernetCredentialVault
from fm_assistant.evolution_onboarding import EvolutionOnboarding
from fm_assistant.evolution_runtime import EvolutionRuntime
from fm_assistant.whatsapp_repository import WhatsAppInboundRepository

SIGNER = "synthetic-ingress-signing-key-" + "h" * 32
INSTANCE_TOKEN = "synthetic-individual-token-xxxxxxxx"


def _auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _signed(cid: str, event: dict) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    signed = b"POST\n/webhooks/fm-evolution/" + cid.encode() + b"\n" + timestamp.encode() + b"\n" + raw
    signature = hmac.new(SIGNER.encode(), signed, hashlib.sha256).hexdigest()
    return raw, {
        "X-FM-Evolution-Signature": signature,
        "X-FM-Evolution-Timestamp": timestamp,
        "Content-Type": "application/json",
    }


def test_signed_webhook_connects_and_replies_once(client, provision_credential):
    key = provision_credential(client, "tenant-evolution", "unit-evolution")
    calls = []

    def provider(request):
        calls.append((request.url.path, request.headers["apikey"]))
        if request.url.path == "/instance/create":
            return httpx.Response(201, json={"hash": {"token": INSTANCE_TOKEN}})
        if request.url.path.startswith("/message/sendText/"):
            assert request.headers["apikey"] == INSTANCE_TOKEN
            return httpx.Response(200, json={"key": {"id": "OUT-1"}})
        return httpx.Response(503)

    transport = EvolutionClient(
        EvolutionSettings(
            origin="https://evolution.example.test", global_key="f" * 40,
        ),
        client=httpx.Client(transport=httpx.MockTransport(provider)),
    )
    vault = FernetCredentialVault(client.app.state.settings.channel_encryption_key)
    repo = client.app.state.integration_repository
    client.app.state.evolution_onboarding = EvolutionOnboarding(
        repository=repo, vault=vault, transport=transport,
    )
    client.app.state.evolution_runtime = EvolutionRuntime(
        integrations=repo,
        inbox=WhatsAppInboundRepository(client.app.state.integration_repository._session_factory),
        assistant=client.app.state.assistant_service,
        vault=vault, transport=transport,
        verifier=EvolutionEventVerifier(signing_key=SIGNER),
        sender_pepper=client.app.state.settings.credential_pepper,
    )
    created = client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_auth(key),
    )
    assert created.status_code == 200, created.text
    cid = created.json()["connection_id"]
    instance = created.json()["config"]["instance_name"]

    # A connected status only comes from a separately authenticated event.
    event = {"event": "connection.update", "instance": instance,
             "data": {"state": "open"}}
    body, headers = _signed(cid, event)
    assert client.post(
        f"/webhooks/fm-evolution/{cid}", content=body, headers=headers,
    ).status_code == 204

    persona = client.put(
        "/v1/persona", headers=_auth(key),
        json={"public_name": "Atendente", "language": "pt-BR", "tone": "consultivo"},
    )
    assert persona.status_code == 200, persona.text
    message = {
        "event": "messages.upsert", "instance": instance,
        "data": [{
            "key": {"id": "WA-001", "fromMe": False,
                    "remoteJid": "5511999999999@s.whatsapp.net"},
            "message": {"conversation": "Olá, quero comprar"},
        }],
    }
    body, headers = _signed(cid, message)
    endpoint = f"/webhooks/fm-evolution/{cid}"
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    outbound = [call for call in calls if call[0].startswith("/message/sendText/")]
    assert len(outbound) == 1
    assert outbound[0][1] == INSTANCE_TOKEN

    # Signed payload cannot be replayed against another instance.
    message["instance"] = "fm_" + "0" * 32
    altered, headers = _signed(cid, message)
    assert client.post(endpoint, content=altered, headers=headers).status_code == 401
    assert client.post(endpoint, content=body).status_code == 401
    assert len([c for c in calls if c[0].startswith("/message/sendText/")]) == 1


def test_unconfigured_webhook_denied(client):
    assert client.post(
        "/webhooks/fm-evolution/ba52d5cb-3742-4b75-916c-a7bdc3c4df20",
        json={"event": "messages.upsert"},
    ).status_code == 503
