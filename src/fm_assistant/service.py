"""Casos de uso do SaaS universal de atendimento."""

from __future__ import annotations

from datetime import UTC, datetime

from .domain import (
    AssistantPersona,
    Channel,
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    TenantContext,
)
from .ports import (
    AuditSink,
    CapabilityProvider,
    ConversationRepository,
    ModelGateway,
    PersonaRepository,
)


class AssistantService:
    def __init__(
        self,
        *,
        personas: PersonaRepository,
        conversations: ConversationRepository,
        model: ModelGateway,
        capabilities: CapabilityProvider,
        audit: AuditSink,
    ) -> None:
        self._personas = personas
        self._conversations = conversations
        self._model = model
        self._capabilities = capabilities
        self._audit = audit

    def get_persona(self, context: TenantContext) -> AssistantPersona | None:
        return self._personas.get(context)

    def configure_persona(
        self,
        *,
        context: TenantContext,
        public_name: str,
        language: str,
        tone: str,
        instructions: str,
        enabled: bool,
    ) -> AssistantPersona:
        persona = AssistantPersona(
            tenant_id=context.tenant_id,
            unit_id=context.unit_id,
            public_name=public_name,
            language=language,
            tone=tone,
            instructions=instructions,
            enabled=enabled,
            updated_at=datetime.now(UTC),
        )
        saved = self._personas.upsert(context, persona)
        self._audit.record(
            context=context,
            action="assistant.persona.configure",
            resource_type="assistant_persona",
            resource_id=None,
            outcome="success",
        )
        return saved

    def create_conversation(
        self,
        *,
        context: TenantContext,
        channel: Channel,
        external_ref: str | None,
    ) -> Conversation:
        persona = self._personas.get(context)
        if persona is None or not persona.enabled:
            raise RuntimeError("assistant_not_configured_or_disabled")
        conversation = Conversation.new(
            tenant_id=context.tenant_id,
            unit_id=context.unit_id,
            channel=channel,
            external_ref=external_ref,
        )
        saved = self._conversations.create(context, conversation)
        self._audit.record(
            context=context,
            action="assistant.conversation.create",
            resource_type="conversation",
            resource_id=saved.conversation_id,
            outcome="success",
            metadata={"channel": channel.value},
        )
        return saved

    def get_conversation(
        self,
        *,
        context: TenantContext,
        conversation_id: str,
    ) -> Conversation:
        conversation = self._conversations.get(context, conversation_id)
        if conversation is None:
            raise LookupError("conversation_not_found")
        return conversation

    def send_message(
        self,
        *,
        context: TenantContext,
        conversation_id: str,
        content: str,
    ) -> Message:
        conversation = self.get_conversation(
            context=context,
            conversation_id=conversation_id,
        )
        if conversation.status is not ConversationStatus.OPEN:
            raise RuntimeError("conversation_not_open")

        persona = self._personas.get(context)
        if persona is None or not persona.enabled:
            raise RuntimeError("assistant_not_configured_or_disabled")

        user_message = Message.new(
            conversation_id=conversation.conversation_id,
            tenant_id=context.tenant_id,
            unit_id=context.unit_id,
            role=MessageRole.USER,
            content=content,
        )
        self._conversations.save_message(context, user_message)
        history = self._conversations.list_messages(
            context,
            conversation.conversation_id,
            limit=50,
        )
        capability_context = self._capabilities.context_for(
            context=context,
            conversation=conversation,
            user_message=user_message,
        )

        try:
            response_text = self._model.generate(
                persona=persona,
                conversation=conversation,
                history=history,
                user_message=user_message,
                capability_context=capability_context,
            )
        except Exception:
            self._audit.record(
                context=context,
                action="assistant.message.generate",
                resource_type="conversation",
                resource_id=conversation_id,
                outcome="failure",
            )
            raise

        assistant_message = Message.new(
            conversation_id=conversation.conversation_id,
            tenant_id=context.tenant_id,
            unit_id=context.unit_id,
            role=MessageRole.ASSISTANT,
            content=response_text,
        )
        self._conversations.save_message(context, assistant_message)
        self._audit.record(
            context=context,
            action="assistant.message.generate",
            resource_type="conversation",
            resource_id=conversation_id,
            outcome="success",
        )
        return assistant_message

    def history(
        self,
        *,
        context: TenantContext,
        conversation_id: str,
    ) -> tuple[Message, ...]:
        self.get_conversation(context=context, conversation_id=conversation_id)
        return self._conversations.list_messages(context, conversation_id, limit=200)

    def handoff(
        self,
        *,
        context: TenantContext,
        conversation_id: str,
        reason: str,
    ) -> Conversation:
        if not reason.strip():
            raise ValueError("handoff_reason_required")
        conversation = self._conversations.set_handoff(context, conversation_id)
        self._audit.record(
            context=context,
            action="assistant.conversation.handoff",
            resource_type="conversation",
            resource_id=conversation_id,
            outcome="success",
            metadata={"reason": reason[:240]},
        )
        return conversation
