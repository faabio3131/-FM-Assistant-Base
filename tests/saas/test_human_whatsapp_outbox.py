"""Only F5 WhatsApp human outbound: encrypted destination and no automatic retry."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import test_human_inbox as fixtures
from sqlalchemy import select
from test_human_inbox import principal

from fm_assistant.db import (
    ConversationORM,
    IntegrationConnectionORM,
    IntegrationProviderORM,
    MessageORM,
)
from fm_assistant.human_inbox import HumanInboxDenied
from fm_assistant.human_whatsapp_outbox import (
    HumanWhatsAppContactORM,
    HumanWhatsAppOutbox,
    HumanWhatsAppOutboxORM,
)


class FakeVault:
    def encrypt(self, value):
        return "encrypted:" + value[::-1]

    def decrypt(self, value):
        assert value.startswith("encrypted:")
        return value.removeprefix("encrypted:")[::-1]


class FakeIntegrations:
    def active_secret_ciphertexts(self, connection_id):
        assert connection_id == "evolution-1"
        return {"instance_token": FakeVault().encrypt("token-private")}


class FakeTransport:
    def __init__(self, *, fail=False):
        self.sent = []
        self.fail = fail

    def send_text(self, instance, *, instance_token, recipient, message):
        self.sent.append((instance, instance_token, recipient, message))
        if self.fail:
            raise RuntimeError("provider result ambiguous")
        return "provider-ref-" + str(len(self.sent))


@pytest.fixture
def configured(tmp_path):
    base_fixture = fixtures.environment.__wrapped__(tmp_path)
    inbox, sessions = next(base_fixture)
    vault = FakeVault()
    outbox = HumanWhatsAppOutbox(sessions, vault, sender_pepper="private-pepper")
    with sessions.begin() as db:
        now = datetime.now(UTC)
        db.add(IntegrationProviderORM(
            provider_key="whatsapp_evolution", integration_type="whatsapp",
            display_name="Evolution", definition_version=1,
            enabled=True, created_at=now, updated_at=now,
        ))
        db.add(IntegrationConnectionORM(
            connection_id="evolution-1", tenant_id="tenant-a", unit_id="unit-1",
            provider_key="whatsapp_evolution", integration_type="whatsapp",
            status="active", config_json=json.dumps({"instance_name": "unit1"}),
            revision=1, created_at=now, updated_at=now,
        ))
        conv = db.get(ConversationORM, "conversation-tenant-a")
        sender = "5511987654321"
        signature = hmac.new(b"private-pepper", f"evolution-1:{sender}".encode(),
                             hashlib.sha256).hexdigest()
        conv.external_ref = f"wae:evolution-1:{signature}"
    inbox.claim(principal=principal(), conversation_id="conversation-tenant-a")
    outbox.bind_verified_inbound(
        tenant_id="tenant-a", unit_id="unit-1",
        conversation_id="conversation-tenant-a", connection_id="evolution-1",
        sender=sender, external_ref=f"wae:evolution-1:{signature}",
    )
    yield inbox, sessions, outbox
    next(base_fixture, None)


def test_encrypted_contact_bind_and_provider_ack(configured):
    _inbox, sessions, outbox = configured
    user = principal()
    identifier = str(uuid4())
    result = outbox.enqueue(principal=user, conversation_id="conversation-tenant-a",
                            message_id=identifier, content="Confirmamos seu pedido.")
    assert result["status"] == "pending"
    with sessions() as db:
        row = db.get(HumanWhatsAppOutboxORM, identifier)
        bound = db.get(HumanWhatsAppContactORM, "conversation-tenant-a")
        assert "5511987654321" not in row.encrypted_recipient
        assert "Confirmamos seu pedido." not in row.encrypted_message
        assert "5511987654321" not in bound.encrypted_recipient
    assert outbox.enqueue(
        principal=user, conversation_id="conversation-tenant-a",
        message_id=identifier, content="Confirmamos seu pedido.",
    )["status"] == "pending"
    transport = FakeTransport()
    done = outbox.process_one(integrations=FakeIntegrations(), transport=transport)
    assert done["status"] == "provider_acknowledged"
    assert transport.sent == [(
        "unit1", "token-private", "5511987654321", "Confirmamos seu pedido.",
    )]
    assert outbox.process_one(integrations=FakeIntegrations(), transport=transport) is None
    assert len(transport.sent) == 1
    assert outbox.status(
        principal=user, conversation_id="conversation-tenant-a",
        message_id=identifier,
    )["provider_reference"] == "provider-ref-1"
    with sessions() as db:
        assert db.get(MessageORM, identifier).role == "assistant"


def test_ambiguous_send_never_retries_or_returns_to_ai(configured):
    inbox, sessions, outbox = configured
    user = principal()
    identifier = str(uuid4())
    outbox.enqueue(principal=user, conversation_id="conversation-tenant-a",
                   message_id=identifier, content="Resposta importante.")
    transport = FakeTransport(fail=True)
    result = outbox.process_one(integrations=FakeIntegrations(), transport=transport)
    assert result["status"] == "sending_uncertain"
    assert len(transport.sent) == 1
    assert outbox.process_one(integrations=FakeIntegrations(), transport=transport) is None
    assert len(transport.sent) == 1
    with pytest.raises(HumanInboxDenied, match="outbound_pending_or_uncertain"):
        inbox.return_to_ai(principal=user, conversation_id="conversation-tenant-a")
    with sessions() as db:
        assert db.scalars(select(MessageORM)).all() == []


def test_inbound_proof_and_tenant_scope_cannot_be_spoofed(configured):
    _inbox, _sessions, outbox = configured
    user = principal()
    with pytest.raises(HumanInboxDenied, match="sender_binding_mismatch"):
        outbox.bind_verified_inbound(
            tenant_id="tenant-a", unit_id="unit-1",
            conversation_id="conversation-tenant-a", connection_id="evolution-1",
            sender="5511888888888", external_ref="wae:evolution-1:forged",
        )
    identifier = str(uuid4())
    outbox.enqueue(principal=user, conversation_id="conversation-tenant-a",
                   message_id=identifier, content="Somente para o cliente correto")
    with pytest.raises(HumanInboxDenied, match="not_found"):
        outbox.status(
            principal=principal(tenant="tenant-b"), conversation_id="conversation-tenant-a",
            message_id=identifier,
        )
    with pytest.raises(HumanInboxDenied, match="reply_idempotency_conflict"):
        outbox.enqueue(principal=user, conversation_id="conversation-tenant-a",
                       message_id=identifier, content="Outra mensagem diferente")
