"""Portas independentes de framework e domínio vertical."""

from __future__ import annotations

from typing import Protocol

from .domain import AssistantPersona, Channel, Conversation, Message, TenantContext


class PersonaRepository(Protocol):
    def get(self, context: TenantContext) -> AssistantPersona | None: ...
    def upsert(self, context: TenantContext, persona: AssistantPersona) -> AssistantPersona: ...


class ConversationRepository(Protocol):
    def create(self, context: TenantContext, conversation: Conversation) -> Conversation: ...
    def get(self, context: TenantContext, conversation_id: str) -> Conversation | None: ...
    def get_by_external_ref(
        self,
        context: TenantContext,
        *,
        channel: Channel,
        external_ref: str,
    ) -> Conversation | None: ...
    def save_message(self, context: TenantContext, message: Message) -> Message: ...
    def list_messages(
        self,
        context: TenantContext,
        conversation_id: str,
        *,
        limit: int = 50,
    ) -> tuple[Message, ...]: ...
    def set_handoff(
        self,
        context: TenantContext,
        conversation_id: str,
    ) -> Conversation: ...


class ModelGateway(Protocol):
    def generate(
        self,
        *,
        persona: AssistantPersona,
        conversation: Conversation,
        history: tuple[Message, ...],
        user_message: Message,
        capability_context: str,
    ) -> str: ...


class CapabilityProvider(Protocol):
    def context_for(
        self,
        *,
        context: TenantContext,
        conversation: Conversation,
        user_message: Message,
    ) -> str: ...


class AuditSink(Protocol):
    def record(
        self,
        *,
        context: TenantContext,
        action: str,
        resource_type: str,
        resource_id: str | None,
        outcome: str,
        metadata: dict[str, str | int | bool] | None = None,
    ) -> None: ...
