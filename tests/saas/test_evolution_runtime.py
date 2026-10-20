"""Synthetic signed webhook -> Assistant conversation -> per-instance WhatsApp outbound."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx
import pytest

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

    # The exact same signed connection update cannot be applied twice.
    assert client.post(
        f"/webhooks/fm-evolution/{cid}", content=body, headers=headers,
    ).status_code == 204
    from fm_assistant.domain import TenantContext
    from fm_assistant.integration import IntegrationStatus

    scoped = TenantContext(
        tenant_id="tenant-evolution", unit_id="unit-evolution", credential_id=key,
    )
    repo.update_connection(scoped, cid, status=IntegrationStatus.DEGRADED)
    assert client.post(
        f"/webhooks/fm-evolution/{cid}", content=body, headers=headers,
    ).status_code == 204
    assert repo.get(scoped, cid).status is IntegrationStatus.DEGRADED

    # A distinct valid notification (new authenticated event body)
    # can return the provider from degraded to active.
    changed = {"event": "connection.update", "instance": instance,
               "data": {"state": "open", "reason": "fresh_notification"}}
    changed_body, changed_headers = _signed(cid, changed)
    assert client.post(
        f"/webhooks/fm-evolution/{cid}",
        content=changed_body, headers=changed_headers,
    ).status_code == 204
    assert repo.get(scoped, cid).status is IntegrationStatus.ACTIVE

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

    # A delayed but valid signed event is NOT allowed to undo an explicit
    # local pause or cause a second outgoing message.
    paused = client.post(
        f"/v1/channels/whatsapp/qr/{cid}/pause", headers=_auth(key),
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "disabled"
    event_body, event_headers = _signed(
        cid, {"event": "connection.update", "instance": instance,
              "data": {"state": "open"}},
    )
    assert client.post(
        endpoint, content=event_body, headers=event_headers,
    ).status_code == 401
    original_message = {
        "event": "messages.upsert", "instance": instance,
        "data": [{"key": {"id": "WA-PAUSED", "fromMe": False,
                           "remoteJid": "5511999999999@s.whatsapp.net"},
                  "message": {"conversation": "Este canal está pausado"}}],
    }
    stopped_body, stopped_headers = _signed(cid, original_message)
    assert client.post(
        endpoint, content=stopped_body, headers=stopped_headers,
    ).status_code == 401
    assert len([c for c in calls if c[0].startswith("/message/sendText/")]) == 1


def test_unconfigured_webhook_denied(client):
    assert client.post(
        "/webhooks/fm-evolution/ba52d5cb-3742-4b75-916c-a7bdc3c4df20",
        json={"event": "messages.upsert"},
    ).status_code == 503


def test_uncertain_outbound_is_quarantined_without_resend(client, provision_credential):
    key = provision_credential(client, "tenant-fail-safe", "unit-fail-safe")
    attempts = []

    def provider(request):
        if request.url.path == "/instance/create":
            return httpx.Response(201, json={"hash": {"token": INSTANCE_TOKEN}})
        if request.url.path.startswith("/message/sendText/"):
            attempts.append(request.url.path)
            return httpx.Response(503, json={"error": "unknown"})
        return httpx.Response(503)

    transport = EvolutionClient(
        EvolutionSettings(
            origin="https://evolution.example.test", global_key="f" * 40,
        ),
        client=httpx.Client(transport=httpx.MockTransport(provider)),
    )
    vault = FernetCredentialVault(client.app.state.settings.channel_encryption_key)
    repository = client.app.state.integration_repository
    client.app.state.evolution_onboarding = EvolutionOnboarding(
        repository=repository, vault=vault, transport=transport,
    )
    inbox = WhatsAppInboundRepository(repository._session_factory)
    client.app.state.evolution_runtime = EvolutionRuntime(
        integrations=repository, inbox=inbox,
        assistant=client.app.state.assistant_service,
        vault=vault, transport=transport,
        verifier=EvolutionEventVerifier(signing_key=SIGNER),
        sender_pepper=client.app.state.settings.credential_pepper,
    )
    created = client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_auth(key),
    )
    assert created.status_code == 200
    cid = created.json()["connection_id"]
    instance = created.json()["config"]["instance_name"]
    body, headers = _signed(
        cid, {"event": "connection.update", "instance": instance,
              "data": {"state": "open"}},
    )
    assert client.post(
        f"/webhooks/fm-evolution/{cid}", content=body, headers=headers,
    ).status_code == 204
    assert client.put(
        "/v1/persona", headers=_auth(key),
        json={"public_name": "Atendente", "language": "pt-BR", "tone": "consultivo"},
    ).status_code == 200
    message = {
        "event": "messages.upsert", "instance": instance,
        "data": [{"key": {
            "id": "WA-UNCERTAIN", "fromMe": False,
            "remoteJid": "5511999999999@s.whatsapp.net",
        }, "message": {"conversation": "Preciso de ajuda"}}],
    }
    body, headers = _signed(cid, message)
    endpoint = f"/webhooks/fm-evolution/{cid}"
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    assert inbox.status(channel_id=cid, message_id="WA-UNCERTAIN") == "reconcile_required"
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    assert len(attempts) == 1


def test_signed_webhook_queues_without_sending_until_worker(client, provision_credential, monkeypatch):
    """Verify HTTP acknowledgment cannot trigger AI/provider on its own."""
    from fm_assistant.evolution_queue import EvolutionInboundQueue

    key = provision_credential(client, "tenant-asynchronous", "unit-asynchronous")
    sent = []

    def provider(request):
        if request.url.path == "/instance/create":
            return httpx.Response(201, json={"hash": {"token": INSTANCE_TOKEN}})
        if request.url.path.startswith("/message/sendText/"):
            sent.append(request.url.path)
            return httpx.Response(200, json={"key": {"id": "ASYNC-OUT-1"}})
        return httpx.Response(503)

    transport = EvolutionClient(
        EvolutionSettings(origin="https://evolution.example.test", global_key="f" * 40),
        client=httpx.Client(transport=httpx.MockTransport(provider)),
    )
    vault = FernetCredentialVault(client.app.state.settings.channel_encryption_key)
    repository = client.app.state.integration_repository
    client.app.state.evolution_onboarding = EvolutionOnboarding(
        repository=repository, vault=vault, transport=transport,
    )
    queue = EvolutionInboundQueue(repository._session_factory, vault)
    runtime = EvolutionRuntime(
        integrations=repository,
        inbox=WhatsAppInboundRepository(repository._session_factory),
        assistant=client.app.state.assistant_service,
        vault=vault, transport=transport,
        verifier=EvolutionEventVerifier(signing_key=SIGNER),
        sender_pepper=client.app.state.settings.credential_pepper,
        queue=queue,
    )
    client.app.state.evolution_runtime = runtime
    created = client.post(
        "/v1/channels/whatsapp/qr/provision", headers=_auth(key),
    )
    assert created.status_code == 200
    cid = created.json()["connection_id"]
    instance = created.json()["config"]["instance_name"]
    body, headers = _signed(
        cid, {"event": "connection.update", "instance": instance,
              "data": {"state": "open"}},
    )
    endpoint = f"/webhooks/fm-evolution/{cid}"
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    assert client.put(
        "/v1/persona", headers=_auth(key),
        json={"public_name": "Atendente", "language": "pt-BR", "tone": "consultivo"},
    ).status_code == 200
    body, headers = _signed(
        cid, {"event": "messages.upsert", "instance": instance,
              "data": [{"key": {
                  "id": "ASYNC-001", "fromMe": False,
                  "remoteJid": "5511999999999@s.whatsapp.net",
              }, "message": {"conversation": "Quero orçamento"}}]},
    )
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    assert queue.state(connection_id=cid, message_id="ASYNC-001") == "pending"
    assert sent == []
    result = runtime.process_pending(limit=5)
    assert result.processed == 1
    assert result.reconcile_required == 0
    assert sent == ["/message/sendText/" + instance]
    assert queue.state(connection_id=cid, message_id="ASYNC-001") == "complete"
    assert runtime.process_pending(limit=5).processed == 0
    assert len(sent) == 1



    # Pause wins after durable intent, before HTTP: no provider attempt.
    from fm_assistant.domain import TenantContext
    from fm_assistant.integration import IntegrationStatus

    body, headers = _signed(
        cid, {"event": "messages.upsert", "instance": instance,
              "data": [{"key": {"id": "PAUSE-RACE-1", "fromMe": False,
                               "remoteJid": "5511999999999@s.whatsapp.net"},
                        "message": {"conversation": "Race with pause"}}]},
    )
    assert client.post(endpoint, content=body, headers=headers).status_code == 204
    original_begin = queue.begin_outbound
    scoped = TenantContext(
        tenant_id="tenant-asynchronous", unit_id="unit-asynchronous",
        credential_id=key,
    )

    def pause_after_intent(**kwargs):
        attempt_id = original_begin(**kwargs)
        repository.update_connection(
            scoped, cid, status=IntegrationStatus.DISABLED, bump_revision=True,
        )
        return attempt_id

    monkeypatch.setattr(queue, "begin_outbound", pause_after_intent)
    result = runtime.process_pending(limit=1)
    assert result.reconcile_required == 1
    assert len(sent) == 1
    assert queue.state(connection_id=cid, message_id="PAUSE-RACE-1") == "reconcile_required"
    assert queue.acknowledge_reconciliation(
        connection_id=cid, message_id="PAUSE-RACE-1",
    ) is False


def test_signed_delivery_updates_match_only_existing_scoped_receipts(
    client, provision_credential,
):
    from fm_assistant.domain import TenantContext
    from fm_assistant.evolution_queue import EvolutionInboundQueue
    from fm_assistant.integration import WHATSAPP_EVOLUTION_PROVIDER, IntegrationStatus

    key = provision_credential(client, "status-tenant", "status-unit")
    ctx = TenantContext(tenant_id="status-tenant", unit_id="status-unit", credential_id=key)
    repo = client.app.state.integration_repository
    connection = repo.create_connection(
        ctx, provider=WHATSAPP_EVOLUTION_PROVIDER,
        config={"instance_name": "fm_" + "e" * 32},
        status=IntegrationStatus.ACTIVE,
    )
    cid = connection.connection_id
    vault = FernetCredentialVault(client.app.state.settings.channel_encryption_key)
    queue = EvolutionInboundQueue(repo._session_factory, vault)
    runtime = EvolutionRuntime(
        integrations=repo,
        inbox=WhatsAppInboundRepository(repo._session_factory),
        assistant=client.app.state.assistant_service,
        vault=vault,
        transport=EvolutionClient(
            EvolutionSettings(
                origin="https://evolution.example.test", global_key="f" * 40,
            ),
            client=httpx.Client(transport=httpx.MockTransport(
                lambda _: httpx.Response(503),
            )),
        ),
        verifier=EvolutionEventVerifier(signing_key=SIGNER),
        sender_pepper=client.app.state.settings.credential_pepper,
        queue=queue,
    )
    assert queue.enqueue(
        connection_id=cid, message_id="inbound-for-receipt",
        sender="5511999999999", text="Secret",
    )
    item = queue.claim()
    assert item is not None
    operation_id = queue.begin_outbound(
        connection_id=cid, message_id=item.message_id,
        claim_generation=item.claim_generation,
    )
    queue.record_outbound_result(
        connection_id=cid, message_id=item.message_id,
        claim_generation=item.claim_generation,
        operation_id=operation_id, outbound_reference="PROVIDER-RECEIPT-ID",
    )
    queue.finish(
        connection_id=cid, message_id=item.message_id,
        reconciled=True, claim_generation=item.claim_generation,
    )
    event = {
        "event": "messages.update",
        "instance": connection.config["instance_name"],
        "data": [{"key": {"id": "PROVIDER-RECEIPT-ID", "fromMe": True},
                  "update": {"status": "DELIVERED"}}],
    }
    raw, headers = _signed(cid, event)
    with pytest.raises(ValueError):
        runtime.receive(
            connection_id=cid, raw=raw,
            signature="0" * 64,
            timestamp=headers["X-FM-Evolution-Timestamp"],
        )
    assert queue.operational_snapshot(connection_id=cid)["lifecycle"][0]["delivery_status"] is None
    runtime.receive(
        connection_id=cid, raw=raw,
        signature=headers["X-FM-Evolution-Signature"],
        timestamp=headers["X-FM-Evolution-Timestamp"],
    )
    verified = queue.operational_snapshot(connection_id=cid)["lifecycle"][0]
    assert verified["delivery_status"] == "delivered"
    assert verified["delivery_evidence_sha256"] == hashlib.sha256(raw).hexdigest()
    assert queue.acknowledge_reconciliation(
        connection_id=cid, message_id=item.message_id,
    )
    raw, headers = _signed(cid, {
        **event, "data": [{"key": {"id": "PROVIDER-RECEIPT-ID", "fromMe": True},
                          "update": {"status": "SENT"}}],
    })
    runtime.receive(
        connection_id=cid, raw=raw,
        signature=headers["X-FM-Evolution-Signature"],
        timestamp=headers["X-FM-Evolution-Timestamp"],
    )
    assert queue.operational_snapshot(connection_id=cid)["lifecycle"][0]["delivery_status"] == "delivered"

