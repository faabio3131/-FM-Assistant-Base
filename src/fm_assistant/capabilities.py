"""Capabilities horizontais; domínios verticais entram por portas, não por imports."""

from __future__ import annotations

from .domain import Conversation, Message, TenantContext
from .repositories import KnowledgeRepository


class KnowledgeCapabilityProvider:
    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository

    def context_for(
        self,
        *,
        context: TenantContext,
        conversation: Conversation,
        user_message: Message,
    ) -> str:
        del conversation, user_message
        return self._repository.context(context)
