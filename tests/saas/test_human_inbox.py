"""Human inbox operational smoke: scope, ownership, transfer and safe resume."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.db import (
    Base,
    ConversationORM,
    MembershipORM,
    MembershipUnitORM,
    MessageORM,
    TenantORM,
    UnitORM,
    UserORM,
)
from fm_assistant.human_inbox import (
    HumanInbox,
    HumanInboxDenied,
    HumanInboxEventORM,
)
from fm_assistant.human_inbox_operations import HumanInboxOperations
from fm_assistant.identity import Role
from fm_assistant.identity_repository import SessionPrincipal


def principal(user="operator-a", tenant="tenant-a", unit="unit-1", role=Role.SUPPORT_AGENT):
    return SessionPrincipal(
        session_id="session-" + user, user_id=user, tenant_id=tenant, unit_id=unit,
        membership_id="membership-" + user, role=role,
        email=user + "@example.test", display_name=user,
    )


@pytest.fixture
def environment(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'human-inbox.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with sessions.begin() as db:
        for tenant in ("tenant-a", "tenant-b"):
            db.add(TenantORM(
                tenant_id=tenant, display_name=tenant, slug=tenant,
                status="active", created_at=now, updated_at=now,
            ))
            db.add(UnitORM(
                tenant_id=tenant, unit_id="unit-1", display_name="unit",
                status="active", created_at=now, updated_at=now,
            ))
            db.add(ConversationORM(
                conversation_id="conversation-" + tenant,
                tenant_id=tenant, unit_id="unit-1",
                channel="whatsapp", status="human_handoff", external_ref="wa-1",
                created_at=now, updated_at=now,
            ))
        for who in ("operator-a", "operator-b"):
            db.add(UserORM(
                user_id=who, email=who + "@example.test",
                display_name=who, password_hash="no-login-fixture",
                active=True, created_at=now, updated_at=now,
            ))
            db.add(MembershipORM(
                membership_id="membership-" + who,
                tenant_id="tenant-a", user_id=who,
                role=Role.SUPPORT_AGENT.value,
                active=True, created_at=now, updated_at=now,
            ))
            db.add(MembershipUnitORM(
                membership_id="membership-" + who,
                tenant_id="tenant-a", unit_id="unit-1",
            ))
    yield HumanInbox(sessions), sessions
    engine.dispose()


def test_human_takeover_transfer_note_history_and_return_to_ai(environment):
    inbox, sessions = environment
    first = principal()
    second = principal(user="operator-b")
    wait = inbox.list_queue(principal=first)
    assert len(wait["items"]) == 1
    assert wait["items"][0]["assigned_to"] is None
    claimed = inbox.claim(principal=first, conversation_id="conversation-tenant-a")
    assert claimed["assigned_to"] == "operator-a"
    assert inbox.claim(principal=first, conversation_id="conversation-tenant-a") == claimed
    with pytest.raises(HumanInboxDenied, match="already_assigned"):
        inbox.claim(principal=second, conversation_id="conversation-tenant-a")
    with pytest.raises(HumanInboxDenied, match="note_forbidden"):
        inbox.add_note(principal=second, conversation_id="conversation-tenant-a", note="secret")
    moved = inbox.transfer(
        principal=first, conversation_id="conversation-tenant-a",
        target_user_id="operator-b",
    )
    assert moved["assigned_to"] == "operator-b"
    with pytest.raises(HumanInboxDenied, match="return_forbidden"):
        inbox.return_to_ai(principal=first, conversation_id="conversation-tenant-a")
    note = inbox.add_note(
        principal=second, conversation_id="conversation-tenant-a",
        note="Waiting for customer confirmation",
    )
    assert note["status"] == "saved"
    activity = inbox.activity(principal=second, conversation_id="conversation-tenant-a")
    assert [e["action"] for e in activity["items"]] == ["note", "transfer", "claim"]
    reopened = inbox.return_to_ai(
        principal=second, conversation_id="conversation-tenant-a",
    )
    assert reopened["status"] == "open"
    assert inbox.list_queue(principal=second)["items"] == []
    with sessions() as db:
        assert db.get(ConversationORM, "conversation-tenant-a").status == "open"
        assert len(db.scalars(select(HumanInboxEventORM)).all()) == 4


def test_foreign_tenant_never_lists_or_claims_conversation(environment):
    inbox, _sessions = environment
    user = principal()
    with pytest.raises(HumanInboxDenied, match="not_found"):
        inbox.claim(principal=user, conversation_id="conversation-tenant-b")
    with pytest.raises(HumanInboxDenied, match="not_found"):
        inbox.activity(principal=user, conversation_id="conversation-tenant-b")
    assert [item["conversation_id"] for item in inbox.list_queue(principal=user)["items"]] == [
        "conversation-tenant-a",
    ]


def test_transfer_requires_real_active_membership_in_same_unit(environment):
    inbox, _sessions = environment
    user = principal()
    inbox.claim(principal=user, conversation_id="conversation-tenant-a")
    with pytest.raises(HumanInboxDenied, match="agent_not_eligible"):
        inbox.transfer(
            principal=user, conversation_id="conversation-tenant-a",
            target_user_id="nonexistent-agent",
        )


def test_human_inbox_has_bounded_page_and_empty_next_page(environment):
    inbox, _sessions = environment
    user = principal()
    assert inbox.list_queue(principal=user, page=1)["items"] == []
    assert inbox.list_queue(principal=user, limit=1)["next_page"] is None
    with pytest.raises(HumanInboxDenied, match="invalid_page"):
        inbox.list_queue(principal=user, limit=101)


def test_human_reply_is_durable_for_webchat_but_not_sent_to_whatsapp(environment):
    inbox, sessions = environment
    agent = principal()
    with sessions.begin() as db:
        db.get(ConversationORM, "conversation-tenant-a").channel = "webchat"
    inbox.claim(principal=agent, conversation_id="conversation-tenant-a")
    message_id = "95942e41-8b45-4b60-a9fe-62d5cb3dc91b"
    result = inbox.reply(
        principal=agent, conversation_id="conversation-tenant-a",
        message_id=message_id, content="Posso ajudar com o seu pedido.",
    )
    assert result == {"status": "stored_for_client", "message_id": message_id}
    same = inbox.reply(
        principal=agent, conversation_id="conversation-tenant-a",
        message_id=message_id, content="Posso ajudar com o seu pedido.",
    )
    assert same["status"] == "already_recorded"
    with pytest.raises(HumanInboxDenied, match="reply_idempotency_conflict"):
        inbox.reply(
            principal=agent, conversation_id="conversation-tenant-a",
            message_id=message_id, content="Outra mensagem.",
        )
    with sessions() as db:
        persisted = db.get(MessageORM, message_id)
        assert persisted.content == "Posso ajudar com o seu pedido."
        assert persisted.role == "assistant"
        assert len(db.scalars(select(MessageORM)).all()) == 1
    inbox.return_to_ai(principal=agent, conversation_id="conversation-tenant-a")
    with pytest.raises(HumanInboxDenied, match="reply_forbidden"):
        inbox.reply(
            principal=agent, conversation_id="conversation-tenant-a",
            message_id="09df7e14-9079-46ba-8184-9d2d02b4c92a",
            content="Depois do retorno.",
        )


def test_whatsapp_reply_fails_closed_until_transporter_is_connected(environment):
    inbox, sessions = environment
    agent = principal()
    inbox.claim(principal=agent, conversation_id="conversation-tenant-a")
    with pytest.raises(HumanInboxDenied, match="channel_delivery_not_connected"):
        inbox.reply(
            principal=agent, conversation_id="conversation-tenant-a",
            message_id="68262ac5-9116-40e9-8460-6a83e7623a11",
            content="Não deve afirmar entrega via WhatsApp.",
        )
    with sessions() as db:
        assert db.scalars(select(MessageORM)).all() == []


def test_unit_sla_policy_is_configurable_without_cross_tenant_leaks(environment):
    inbox, sessions = environment
    operations = HumanInboxOperations(sessions)
    manager = principal(role=Role.MANAGER)
    initial = operations.policy(principal=manager)
    assert initial["revision"] == 0
    assert initial["first_response_minutes"] == 20
    updated = operations.configure(
        principal=manager, first_response_minutes=5,
        presence_timeout_seconds=60, expected_revision=0,
    )
    assert updated["revision"] == 1
    assert inbox.list_queue(principal=manager)["items"][0]["sla_minutes"] == 5
    assert operations.policy(principal=principal(tenant="tenant-b"))["revision"] == 0
    with pytest.raises(HumanInboxDenied, match="sla_revision_conflict"):
        operations.configure(
            principal=manager, first_response_minutes=9,
            presence_timeout_seconds=60, expected_revision=0,
        )
    with pytest.raises(HumanInboxDenied, match="sla_manager_required"):
        operations.configure(
            principal=principal(), first_response_minutes=10,
            presence_timeout_seconds=60, expected_revision=1,
        )


def test_presence_only_lists_active_agent_from_current_tenant_unit(environment):
    _inbox, sessions = environment
    operations = HumanInboxOperations(sessions)
    agent = principal()
    pulse = operations.heartbeat(principal=agent)
    assert pulse["status"] == "online"
    online = operations.online_agents(principal=agent)
    assert [p["user_id"] for p in online["items"]] == ["operator-a"]
    assert operations.online_agents(principal=principal(tenant="tenant-b"))["items"] == []
