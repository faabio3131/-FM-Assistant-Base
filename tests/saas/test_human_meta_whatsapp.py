"""Meta human WhatsApp stays inside VendeAtendeIA and never crosses Evo queue."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import test_human_whatsapp_outbox as source_fixtures
from test_human_inbox import principal

from fm_assistant.channels.whatsapp_meta import (
    MetaWhatsAppClient,
    WhatsAppMetaConfig,
    WhatsAppProviderError,
)
from fm_assistant.db import ConversationORM, IntegrationConnectionORM, IntegrationProviderORM
from fm_assistant.human_inbox import HumanInboxDenied
from fm_assistant.human_whatsapp_outbox import HumanWhatsAppContactORM
from fm_assistant.vendeatendeia_runtime import configure_product


@pytest.fixture
def meta_configured(tmp_path):
    fixture = source_fixtures.configured.__wrapped__(tmp_path)
    inbox, sessions, outbox = next(fixture)
    now = datetime.now(UTC)
    sender = "5511987654321"
    digest = hmac.new(b"private-pepper", f"evolution-1:{sender}".encode(),
                      hashlib.sha256).hexdigest()
    with sessions.begin() as db:
        db.add(IntegrationProviderORM(
            provider_key="whatsapp_meta", integration_type="whatsapp",
            display_name="Meta Cloud", definition_version=1,
            enabled=True, created_at=now, updated_at=now,
        ))
        connection = db.get(IntegrationConnectionORM, "evolution-1")
        connection.provider_key = "whatsapp_meta"
        connection.config_json = json.dumps({"phone_number_id": "phone-123"})
        db.get(ConversationORM, "conversation-tenant-a").external_ref = (
            f"wa:evolution-1:{digest}"
        )
    outbox.bind_verified_inbound(
        tenant_id="tenant-a", unit_id="unit-1",
        conversation_id="conversation-tenant-a",
        connection_id="evolution-1", sender=sender,
        external_ref=f"wa:evolution-1:{digest}",
        provider_key="whatsapp_meta",
    )
    config = WhatsAppMetaConfig(
        channel_id="evolution-1", tenant_id="tenant-a", unit_id="unit-1",
        phone_number_id="phone-123", business_account_id="waba-123",
        access_token="fake-access", app_secret="signed-app-secret",
        verify_token="verify-token", graph_api_version="v23.0",
    )

    class Channels:
        def get_by_channel_id(self, connection_id):
            assert connection_id == "evolution-1"
            return config

    yield inbox, sessions, outbox, config, Channels()
    next(fixture, None)


def test_meta_outbound_only_meta_worker_can_claim(meta_configured, monkeypatch):
    _inbox, sessions, outbox, config, channels = meta_configured
    message_id = str(uuid4())
    queued = outbox.enqueue(
        principal=principal(), conversation_id="conversation-tenant-a",
        message_id=message_id, content="Atendimento humano confirmado.",
    )
    assert queued["status"] == "pending"
    assert outbox.process_one(integrations=None, transport=None) is None

    sends = []

    def mock_meta_send(self, *, recipient, text, correlation_id):
        sends.append((recipient, text, correlation_id, self._config.phone_number_id))
        return "wamid-meta-out-1"

    monkeypatch.setattr(MetaWhatsAppClient, "send_text", mock_meta_send)
    done = outbox.process_one(provider_key="whatsapp_meta", channels=channels)
    assert done["status"] == "provider_acknowledged"
    assert sends == [(
        "5511987654321", "Atendimento humano confirmado.", message_id, config.phone_number_id
    )]
    assert outbox.process_one(provider_key="whatsapp_meta", channels=channels) is None
    assert len(sends) == 1
    state = outbox.status(
        principal=principal(), conversation_id="conversation-tenant-a",
        message_id=message_id,
    )
    assert state["provider_reference"] == "wamid-meta-out-1"
    from fm_assistant.db import MessageORM
    with sessions() as db:
        assert db.get(MessageORM, message_id).role == "assistant"


def test_signed_meta_delivery_receipts_are_bound_to_phone_and_exact_reference(
    meta_configured, monkeypatch,
):
    _inbox, _sessions, outbox, config, channels = meta_configured
    message_id = str(uuid4())
    outbox.enqueue(
        principal=principal(), conversation_id="conversation-tenant-a",
        message_id=message_id, content="Pedido concluído",
    )
    monkeypatch.setattr(
        MetaWhatsAppClient, "send_text",
        lambda self, *, recipient, text, correlation_id: "wamid-meta-out-1",
    )
    outbox.process_one(provider_key="whatsapp_meta", channels=channels)
    payload = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "phone-123"},
            "statuses": [{"id": "wamid-meta-out-1", "status": "delivered"}],
        }}]}]
    }).encode()
    signature = "sha256=" + hmac.new(
        config.app_secret.encode(), payload, hashlib.sha256,
    ).hexdigest()
    client = MetaWhatsAppClient(config)
    receipt = client.parse_delivery_statuses(body=payload, signature=signature)
    assert receipt == (("wamid-meta-out-1", "delivered"),)
    for ref, state in receipt:
        assert outbox.correlate_authenticated_status(
            connection_id=config.channel_id, provider_reference=ref,
            delivery_status=state, evidence_sha256=hashlib.sha256(payload).hexdigest(),
        )
    own = outbox.status(
        principal=principal(), conversation_id="conversation-tenant-a",
        message_id=message_id,
    )
    assert own["delivery_status"] == "delivered"
    assert client.parse_delivery_statuses(
        body=payload.replace(b"phone-123", b"other-123"),
        signature="sha256=" + hmac.new(
            config.app_secret.encode(),
            payload.replace(b"phone-123", b"other-123"),
            hashlib.sha256,
        ).hexdigest(),
    ) == ()
    with pytest.raises(WhatsAppProviderError, match="signature_invalid"):
        client.parse_delivery_statuses(body=payload, signature="sha256=" + "0" * 64)


def test_meta_24_hour_window_blocks_old_human_reply(meta_configured, monkeypatch):
    _inbox, sessions, outbox, _config, channels = meta_configured
    message_id = str(uuid4())
    outbox.enqueue(
        principal=principal(), conversation_id="conversation-tenant-a",
        message_id=message_id, content="Resposta fora do período.",
    )
    with sessions.begin() as db:
        db.get(HumanWhatsAppContactORM, "conversation-tenant-a").updated_at = (
            datetime.now(UTC) - timedelta(hours=25)
        )
    sends = []
    monkeypatch.setattr(MetaWhatsAppClient, "send_text",
                        lambda self, **kwargs: sends.append(kwargs))
    assert outbox.process_one(
        provider_key="whatsapp_meta", channels=channels,
    )["status"] == "sending_uncertain"
    assert sends == []
    assert outbox.process_one(provider_key="whatsapp_meta", channels=channels) is None


def test_meta_binding_requires_hmac_and_provider_scope(meta_configured):
    _inbox, sessions, outbox, _config, _channels = meta_configured
    with pytest.raises(HumanInboxDenied, match="sender_binding_mismatch"):
        outbox.bind_verified_inbound(
            tenant_id="tenant-a", unit_id="unit-1",
            conversation_id="conversation-tenant-a",
            connection_id="evolution-1", sender="5511900000000",
            external_ref="wa:evolution-1:forged", provider_key="whatsapp_meta",
        )
    with sessions() as db:
        assert db.get(HumanWhatsAppContactORM, "conversation-tenant-a")


def test_optional_meta_worker_fails_closed_without_db_config():
    base = {
        "FM_VENDEATENDEIA_INTERNAL_KEY": "test-local-strong-secret-1-2-3-4-5-6-7-8",
        "FM_CORE_AI_ROUTES_JSON": "[]",
    }
    assert not configure_product(base).meta_human_outbound_worker
    with pytest.raises(ValueError, match="meta_worker_configuration_incomplete"):
        configure_product({**base, "FM_VENDEATENDEIA_META_WORKER_ENABLED": "true"})
    product = configure_product({
        **base, "FM_VENDEATENDEIA_META_WORKER_ENABLED": "true",
        "FM_ASSISTANT_DATABASE_URL": "sqlite:///./local-assistant.db",
        "FM_ASSISTANT_CHANNEL_ENCRYPTION_KEY": "local-vault",
        "FM_ASSISTANT_CREDENTIAL_PEPPER": "local-pepper",
    })
    assert product.meta_human_outbound_worker
    assert not product.evolution_human_outbound_worker
