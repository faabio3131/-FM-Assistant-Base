from __future__ import annotations

import httpx

from fm_assistant.core_client import CoreAIClient, CoreAudioTranscriber
from fm_assistant.domain import AssistantPersona, Channel, Conversation, Message, MessageRole
from fm_assistant.gateways import CoreModelGateway


def _response(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("POST", "https://core.invalid"),
    )


def test_core_model_gateway_preserves_tenant_scope(monkeypatch):
    calls: list[dict] = []

    def fake_post(url, *, headers, json, timeout):
        calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return _response(
            {
                "content": "resposta roteada pelo Core",
                "provider": "gemini",
                "model": "model-a",
                "fallback_used": False,
                "fallback_reason": None,
                "price_snapshot_id": "price-a",
            }
        )

    monkeypatch.setattr("fm_assistant.core_client.httpx.post", fake_post)

    client = CoreAIClient(
        base_url="https://core.invalid",
        service_key="internal-secret",
    )
    gateway = CoreModelGateway(client)
    conversation = Conversation.new(
        tenant_id="tenant-a",
        unit_id="unit-a",
        channel=Channel.API,
    )
    persona = AssistantPersona(
        tenant_id="tenant-a",
        unit_id="unit-a",
        public_name="Nina",
    )
    user = Message.new(
        conversation_id=conversation.conversation_id,
        tenant_id="tenant-a",
        unit_id="unit-a",
        role=MessageRole.USER,
        content="Olá",
    )

    answer = gateway.generate(
        persona=persona,
        conversation=conversation,
        history=(user,),
        user_message=user,
        capability_context="Produto Alpha existe.",
    )

    assert answer == "resposta roteada pelo Core"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://core.invalid/v1/ai/text"
    assert call["headers"]["X-Core-Service-Key"] == "internal-secret"
    assert call["json"]["tenant_id"] == "tenant-a"
    assert call["json"]["unit_id"] == "unit-a"
    assert call["json"]["correlation_id"] == user.message_id
    assert call["json"]["messages"][-1] == {"role": "user", "content": "Olá"}


def test_core_audio_transcriber_preserves_scope_and_correlation(monkeypatch):
    calls: list[dict] = []

    def fake_post(url, *, headers, json, timeout):
        calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return _response(
            {
                "content": "quero saber mais sobre o produto",
                "provider": "openai",
                "model": "audio-model",
                "fallback_used": True,
                "fallback_reason": "primary_unavailable",
                "price_snapshot_id": "price-audio",
            }
        )

    monkeypatch.setattr("fm_assistant.core_client.httpx.post", fake_post)

    transcriber = CoreAudioTranscriber(
        CoreAIClient(
            base_url="https://core.invalid",
            service_key="internal-secret",
        )
    )

    text = transcriber.transcribe(
        tenant_id="tenant-b",
        unit_id="unit-b",
        correlation_id="wamid-123",
        content=b"audio-data",
        mime_type="audio/ogg",
    )

    assert text == "quero saber mais sobre o produto"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://core.invalid/v1/ai/transcribe"
    assert call["json"]["tenant_id"] == "tenant-b"
    assert call["json"]["unit_id"] == "unit-b"
    assert call["json"]["correlation_id"] == "wamid-123"
    assert call["json"]["mime_type"] == "audio/ogg"
    assert call["json"]["audio_base64"]
