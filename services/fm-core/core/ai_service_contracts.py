"""Contratos provider-neutral da API de IA do FM Core Base."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class TextMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        role = self.role.strip().casefold()
        content = self.content.strip()
        if role not in {"user", "assistant"}:
            raise ValueError("ai_text_role_invalid")
        if not content:
            raise ValueError("ai_text_content_required")
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "content", content)


@dataclass(frozen=True, kw_only=True)
class TextRequestContent:
    system_prompt: str
    messages: tuple[TextMessage, ...]

    def __post_init__(self) -> None:
        if not self.system_prompt.strip():
            raise ValueError("ai_system_prompt_required")
        if not self.messages:
            raise ValueError("ai_messages_required")


@dataclass(frozen=True, kw_only=True)
class CoreAIResult:
    content: str
    provider: str
    model: str
    fallback_used: bool
    fallback_reason: str | None
    price_snapshot_id: str
