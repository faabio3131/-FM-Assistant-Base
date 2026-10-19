"""Offline Evolution v2 per-instance webhook authentication and relink contracts."""
from __future__ import annotations

import json

import httpx

from fm_assistant.channels.evolution_events import EvolutionEventVerifier
from fm_assistant.channels.whatsapp_evolution import EvolutionClient, EvolutionSettings
from fm_assistant.credential_vault import FernetCredentialVault
from fm_assistant.domain import TenantContext
from fm_assistant.evolution_native_ingress import EvolutionNativeIngress
from fm_assistant.evolution_onboarding import EvolutionOnboarding
from fm_assistant.evolution_queue import EvolutionInboundQueue
from fm_assistant.evolution_runtime import EvolutionRuntime
from fm_assistant.integration import IntegrationStatus
from fm_assistant.whatsapp_repository import WhatsAppInboundRepository

SOURCE_BASE = "https://hooks.example.test/webhooks/evolution-native"
SIGNING_KEY = "private-fm-broker-key-" + "x" * 40


def _prepare(client, provision_credential):
    key = provision_credential(client, "tenant-native-a", "unit-native-a")
    other = provision_credential(client, "tenant-native-b", "unit-native-b")
    registered = []
    instances = []

    def provider(req):
        if req.url.path == "/instance/create":
            name = json.loads(req.content)["instanceName"]
            instances.append(name)
            return httpx.Response(201, json={
                "hash": {"token": "synthetic-instance-token-" + "t" * 36},
            })
        if req.url.path.startswith("/webhook/set/"):
            data = json.loads(req.content)
            assert data["webhook"]["headers"]["X-FM-Evolution-Token"]
            assert data["webhook"]["events"] == [
                "MESSAGES_UPSERT", "CONNECTION_UPDATE",
            ]
            registered.append(data["webhook"])
            return httpx.Response(200, json={"webhook": {
                "enabled": True, "url": data["webhook"]["url"],
            }})
        if req.url.path.startswith("/instance/logout/"):
            return httpx.Response(200, json={"status": "success"})
        return httpx.Response(503)

    transport = EvolutionClient(EvolutionSettings(
        origin="https://evolution.example.test", global_key="g" * 40,
    ), client=httpx.Client(transport=httpx.MockTransport(provider)))
    repo = client.app.state.integration_repository
    vault = FernetCredentialVault(client.app.state.settings.channel_encryption_key)
    client.app.state.evolution_onboarding = EvolutionOnboarding(
        repository=repo, vault=vault, transport=transport,
        native_webhook_base_url=SOURCE_BASE,
    )
    queue = EvolutionInboundQueue(repo._session_factory, vault)
    runtime = EvolutionRuntime(
        integrations=repo, inbox=WhatsAppInboundRepository(repo._session_factory),
        assistant=client.app.state.assistant_service, vault=vault,
        transport=transport,
        verifier=EvolutionEventVerifier(signing_key=SIGNING_KEY),
        sender_pepper=client.app.state.settings.credential_pepper,
        queue=queue,
    )
    client.app.state.evolution_runtime = runtime
    client.app.state.evolution_native_ingress = EvolutionNativeIngress(
        repository=repo, vault=vault, runtime=runtime,
        internal_signer=SIGNING_KEY,
    )
    return key, other, registered, instances, repo, queue


def test_native_hook_header_auth_isolated_and_internal_spoof_blocked(client, provision_credential):
    owner, other, hooks, names, repo, queue = _prepare(client, provision_credential)
    created = client.post(
        "/v1/channels/whatsapp/qr/provision",
        headers={"Authorization": "Bearer " + owner},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["connection_id"]
    instance = names[0]
    token = hooks[0]["headers"]["X-FM-Evolution-Token"]
    assert token not in created.text
    endpoint = "/webhooks/evolution-native/" + cid
    event = {"event": "connection.update", "instance": instance,
             "data": {"state": "open"}}
    raw = json.dumps(event).encode()
    assert client.post(endpoint, content=raw).status_code == 401
    assert client.post(endpoint, content=raw, headers={
        "X-FM-Evolution-Token": "wrong-" + "y" * 50,
        "X-FM-Evolution-Signature": "f" * 64,
    }).status_code == 401
    assert client.post(endpoint, content=raw, headers={
        "X-FM-Evolution-Token": token,
        "X-FM-Evolution-Signature": "f" * 64,
        "X-FM-Evolution-Timestamp": "1234567890",
    }).status_code == 204
    scoped = TenantContext(
        tenant_id="tenant-native-a", unit_id="unit-native-a", credential_id=owner,
    )
    assert repo.get(scoped, cid).status is IntegrationStatus.ACTIVE
    event = {"event": "messages.upsert", "instance": "fm_" + "f" * 32,
             "data": []}
    assert client.post(endpoint, content=json.dumps(event).encode(),
                       headers={"X-FM-Evolution-Token": token}).status_code == 401
    event["instance"] = instance
    event["data"] = [{"key": {
        "id": "EDGE-1", "fromMe": False,
        "remoteJid": "5511999999999@s.whatsapp.net",
    }, "message": {"conversation": "Olá"}}]
    raw = json.dumps(event).encode()
    assert client.post(endpoint, content=raw,
                       headers={"X-FM-Evolution-Token": token}).status_code == 204
    assert queue.state(connection_id=cid, message_id="EDGE-1") == "pending"
    assert client.post(endpoint, content=raw,
                       headers={"X-FM-Evolution-Token": token}).status_code == 204
    assert client.post(
        "/v1/channels/whatsapp/qr/" + cid + "/pause",
        headers={"Authorization": "Bearer " + owner},
    ).status_code == 200
    assert client.post(endpoint, content=raw,
                       headers={"X-FM-Evolution-Token": token}).status_code == 401
    assert client.post(
        "/v1/channels/whatsapp/qr/" + cid + "/logout",
        headers={"Authorization": "Bearer " + other},
    ).status_code == 404


def test_verified_logout_allows_new_instance_without_reusing_old_secret(client, provision_credential):
    owner, _other, hooks, names, repo, _queue = _prepare(client, provision_credential)
    headers = {"Authorization": "Bearer " + owner}
    initial = client.post("/v1/channels/whatsapp/qr/provision", headers=headers)
    assert initial.status_code == 200
    cid1 = initial.json()["connection_id"]
    first_token = hooks[0]["headers"]["X-FM-Evolution-Token"]
    removed = client.post(
        "/v1/channels/whatsapp/qr/" + cid1 + "/logout", headers=headers,
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "revoked"
    fresh = client.post("/v1/channels/whatsapp/qr/provision", headers=headers)
    assert fresh.status_code == 200, fresh.text
    cid2 = fresh.json()["connection_id"]
    assert cid1 != cid2
    assert names[0] != names[1]
    assert hooks[1]["headers"]["X-FM-Evolution-Token"] != first_token
    assert repo.active_secret_ciphertexts(cid1) == {}
    assert len(repo.active_secret_ciphertexts(cid2)) == 2
    assert client.post(
        "/webhooks/evolution-native/" + cid1,
        content=json.dumps({"event": "connection.update", "instance": names[0],
                           "data": {"state": "open"}}).encode(),
        headers={"X-FM-Evolution-Token": first_token},
    ).status_code == 401
