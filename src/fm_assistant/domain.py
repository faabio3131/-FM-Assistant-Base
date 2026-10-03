"""Contratos de domínio horizontais da Assistente Base."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class Channel(StrEnum):
    API = "api"
    WEBCHAT = "webchat"
    WHATSAPP = "whatsapp"


class ConversationStatus(StrEnum):
    OPEN = "open"
    HUMAN_HANDOFF = "human_handoff"
    CLOSED = "closed"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True, kw_only=True)
class TenantContext:
    tenant_id: str
    unit_id: str
    credential_id: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "unit_id", "credential_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name}_obrigatorio")


@dataclass(frozen=True, kw_only=True)
class AssistantPersona:
    tenant_id: str
    unit_id: str
    public_name: str
    language: str = "pt-BR"
    tone: str = "profissional"
    instructions: str = ""
    enabled: bool = True
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.public_name.strip():
            raise ValueError("public_name_obrigatorio")
        if not self.language.strip():
            raise ValueError("language_obrigatoria")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at_sem_timezone")


@dataclass(frozen=True, kw_only=True)
class Conversation:
    conversation_id: str
    tenant_id: str
    unit_id: str
    channel: Channel
    status: ConversationStatus
    external_ref: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        *,
        tenant_id: str,
        unit_id: str,
        channel: Channel,
        external_ref: str | None = None,
    ) -> Conversation:
        now = datetime.now(UTC)
        return cls(
            conversation_id=str(uuid4()),
            tenant_id=tenant_id,
            unit_id=unit_id,
            channel=channel,
            status=ConversationStatus.OPEN,
            external_ref=external_ref,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, kw_only=True)
class Message:
    message_id: str
    conversation_id: str
    tenant_id: str
    unit_id: str
    role: MessageRole
    content: str
    created_at: datetime

    @classmethod
    def new(
        cls,
        *,
        conversation_id: str,
        tenant_id: str,
        unit_id: str,
        role: MessageRole,
        content: str,
    ) -> Message:
        text = content.strip()
        if not text:
            raise ValueError("message_content_obrigatorio")
        return cls(
            message_id=str(uuid4()),
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            unit_id=unit_id,
            role=role,
            content=text,
            created_at=datetime.now(UTC),
        )
