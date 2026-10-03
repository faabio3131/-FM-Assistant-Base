"""Repositórios SQLAlchemy com isolamento de tenant aplicado em toda consulta."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from .db import (
    AuditEventORM,
    ConversationORM,
    KnowledgeDocumentORM,
    MessageORM,
    PersonaORM,
    TenantCredentialORM,
)
from .domain import (
    AssistantPersona,
    Channel,
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    TenantContext,
)
from .security import Credential


class CredentialRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        credential_id: str,
        key_hash: str,
    ) -> Credential:
        with self._session_factory() as session:
            row = TenantCredentialORM(
                credential_id=credential_id,
                tenant_id=tenant_id,
                unit_id=unit_id,
                key_hash=key_hash,
                active=True,
            )
            session.add(row)
            session.commit()
            return Credential(
                credential_id=row.credential_id,
                tenant_id=row.tenant_id,
                unit_id=row.unit_id,
                key_hash=row.key_hash,
                active=row.active,
            )

    def resolve_hash(self, key_hash: str) -> Credential | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(TenantCredentialORM).where(
                    TenantCredentialORM.key_hash == key_hash,
                    TenantCredentialORM.active.is_(True),
                )
            )
            if row is None:
                return None
            return Credential(
                credential_id=row.credential_id,
                tenant_id=row.tenant_id,
                unit_id=row.unit_id,
                key_hash=row.key_hash,
                active=row.active,
            )

    def revoke(self, credential_id: str) -> bool:
        with self._session_factory() as session:
            row = session.get(TenantCredentialORM, credential_id)
            if row is None:
                return False
            row.active = False
            session.commit()
            return True


class PersonaSQLAlchemyRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def get(self, context: TenantContext) -> AssistantPersona | None:
        with self._session_factory() as session:
            row = session.get(PersonaORM, (context.tenant_id, context.unit_id))
            if row is None:
                return None
            return AssistantPersona(
                tenant_id=row.tenant_id,
                unit_id=row.unit_id,
                public_name=row.public_name,
                language=row.language,
                tone=row.tone,
                instructions=row.instructions,
                enabled=row.enabled,
                updated_at=row.updated_at.replace(tzinfo=row.updated_at.tzinfo or UTC),
            )

    def upsert(
        self,
        context: TenantContext,
        persona: AssistantPersona,
    ) -> AssistantPersona:
        if persona.tenant_id != context.tenant_id or persona.unit_id != context.unit_id:
            raise PermissionError("persona_fora_do_escopo")
        with self._session_factory() as session:
            row = session.get(PersonaORM, (context.tenant_id, context.unit_id))
            if row is None:
                row = PersonaORM(
                    tenant_id=context.tenant_id,
                    unit_id=context.unit_id,
                    public_name=persona.public_name,
                    language=persona.language,
                    tone=persona.tone,
                    instructions=persona.instructions,
                    enabled=persona.enabled,
                    updated_at=persona.updated_at,
                )
                session.add(row)
            else:
                row.public_name = persona.public_name
                row.language = persona.language
                row.tone = persona.tone
                row.instructions = persona.instructions
                row.enabled = persona.enabled
                row.updated_at = persona.updated_at
            session.commit()
        return persona


class ConversationSQLAlchemyRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _domain(row: ConversationORM) -> Conversation:
        return Conversation(
            conversation_id=row.conversation_id,
            tenant_id=row.tenant_id,
            unit_id=row.unit_id,
            channel=Channel(row.channel),
            status=ConversationStatus(row.status),
            external_ref=row.external_ref,
            created_at=row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
            updated_at=row.updated_at.replace(tzinfo=row.updated_at.tzinfo or UTC),
        )

    def create(self, context: TenantContext, conversation: Conversation) -> Conversation:
        if (
            conversation.tenant_id != context.tenant_id
            or conversation.unit_id != context.unit_id
        ):
            raise PermissionError("conversation_fora_do_escopo")
        with self._session_factory() as session:
            session.add(
                ConversationORM(
                    conversation_id=conversation.conversation_id,
                    tenant_id=conversation.tenant_id,
                    unit_id=conversation.unit_id,
                    channel=conversation.channel.value,
                    status=conversation.status.value,
                    external_ref=conversation.external_ref,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                )
            )
            session.commit()
        return conversation

    def get(self, context: TenantContext, conversation_id: str) -> Conversation | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ConversationORM).where(
                    ConversationORM.conversation_id == conversation_id,
                    ConversationORM.tenant_id == context.tenant_id,
                    ConversationORM.unit_id == context.unit_id,
                )
            )
            return self._domain(row) if row is not None else None

    def get_by_external_ref(
        self,
        context: TenantContext,
        *,
        channel: Channel,
        external_ref: str,
    ) -> Conversation | None:
        reference = external_ref.strip()
        if not reference:
            raise ValueError("external_ref_required")
        with self._session_factory() as session:
            row = session.scalar(
                select(ConversationORM)
                .where(
                    ConversationORM.tenant_id == context.tenant_id,
                    ConversationORM.unit_id == context.unit_id,
                    ConversationORM.channel == channel.value,
                    ConversationORM.external_ref == reference,
                )
                .order_by(ConversationORM.updated_at.desc())
                .limit(1)
            )
            return self._domain(row) if row is not None else None

    def save_message(self, context: TenantContext, message: Message) -> Message:
        if message.tenant_id != context.tenant_id or message.unit_id != context.unit_id:
            raise PermissionError("message_fora_do_escopo")
        if self.get(context, message.conversation_id) is None:
            raise LookupError("conversation_not_found")
        with self._session_factory() as session:
            session.add(
                MessageORM(
                    message_id=message.message_id,
                    conversation_id=message.conversation_id,
                    tenant_id=message.tenant_id,
                    unit_id=message.unit_id,
                    role=message.role.value,
                    content=message.content,
                    created_at=message.created_at,
                )
            )
            row = session.scalar(
                select(ConversationORM).where(
                    ConversationORM.conversation_id == message.conversation_id,
                    ConversationORM.tenant_id == context.tenant_id,
                    ConversationORM.unit_id == context.unit_id,
                )
            )
            assert row is not None
            row.updated_at = message.created_at
            session.commit()
        return message

    def list_messages(
        self,
        context: TenantContext,
        conversation_id: str,
        *,
        limit: int = 50,
    ) -> tuple[Message, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(MessageORM)
                .where(
                    MessageORM.conversation_id == conversation_id,
                    MessageORM.tenant_id == context.tenant_id,
                    MessageORM.unit_id == context.unit_id,
                )
                .order_by(MessageORM.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).all()
        rows = list(reversed(rows))
        return tuple(
            Message(
                message_id=row.message_id,
                conversation_id=row.conversation_id,
                tenant_id=row.tenant_id,
                unit_id=row.unit_id,
                role=MessageRole(row.role),
                content=row.content,
                created_at=row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
            )
            for row in rows
        )

    def set_handoff(
        self,
        context: TenantContext,
        conversation_id: str,
    ) -> Conversation:
        with self._session_factory() as session:
            row = session.scalar(
                select(ConversationORM).where(
                    ConversationORM.conversation_id == conversation_id,
                    ConversationORM.tenant_id == context.tenant_id,
                    ConversationORM.unit_id == context.unit_id,
                )
            )
            if row is None:
                raise LookupError("conversation_not_found")
            row.status = ConversationStatus.HUMAN_HANDOFF.value
            row.updated_at = datetime.now(UTC)
            session.commit()
            return self._domain(row)


class KnowledgeRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def add(self, context: TenantContext, *, title: str, content: str) -> str:
        title = title.strip()
        content = content.strip()
        if not title or not content:
            raise ValueError("knowledge_title_content_required")
        document_id = str(uuid4())
        now = datetime.now(UTC)
        with self._session_factory() as session:
            session.add(
                KnowledgeDocumentORM(
                    document_id=document_id,
                    tenant_id=context.tenant_id,
                    unit_id=context.unit_id,
                    title=title,
                    content=content,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        return document_id

    def context(self, context: TenantContext, *, max_chars: int = 12000) -> str:
        with self._session_factory() as session:
            rows = session.scalars(
                select(KnowledgeDocumentORM)
                .where(
                    KnowledgeDocumentORM.tenant_id == context.tenant_id,
                    KnowledgeDocumentORM.unit_id == context.unit_id,
                    KnowledgeDocumentORM.active.is_(True),
                )
                .order_by(KnowledgeDocumentORM.updated_at.desc())
            ).all()
        chunks: list[str] = []
        used = 0
        for row in rows:
            chunk = f"## {row.title}\n{row.content.strip()}"
            if used + len(chunk) > max_chars:
                break
            chunks.append(chunk)
            used += len(chunk)
        return "\n\n".join(chunks)


class SQLAuditSink:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        context: TenantContext,
        action: str,
        resource_type: str,
        resource_id: str | None,
        outcome: str,
        metadata: dict[str, str | int | bool] | None = None,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                AuditEventORM(
                    audit_id=str(uuid4()),
                    tenant_id=context.tenant_id,
                    unit_id=context.unit_id,
                    credential_id=context.credential_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    outcome=outcome,
                    metadata_json=json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False),
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
