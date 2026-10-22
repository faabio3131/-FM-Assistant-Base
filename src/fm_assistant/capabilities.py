"""Capabilities horizontais; domínios verticais entram por portas, não por imports."""

from __future__ import annotations

from .domain import Conversation, Message, TenantContext
from .repositories import KnowledgeRepository
from .knowledge_retrieval import BoundedKnowledgeRetrieval


class KnowledgeCapabilityProvider:
    def __init__(self, repository: KnowledgeRepository, *,
                 retrieval: BoundedKnowledgeRetrieval | None = None,
                 retrieval_enabled: bool = False) -> None:
        self._repository = repository
        self._retrieval = retrieval
        self._retrieval_enabled = retrieval_enabled

    def context_for(
        self,
        *,
        context: TenantContext,
        conversation: Conversation,
        user_message: Message,
    ) -> str:
        del conversation
        if self._retrieval_enabled:
            if self._retrieval is None:
                raise RuntimeError("f4.retrieval_not_configured")
            return self._retrieval.query(context, user_message.content[:500]).context
        return self._repository.context(context)
