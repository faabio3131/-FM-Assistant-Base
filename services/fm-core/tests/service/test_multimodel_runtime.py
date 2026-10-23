from __future__ import annotations

import httpx

from core.ai_router import CapabilityIA, MedidorUsoIAEmMemoria
from core.ai_service_contracts import TextMessage
from core.ai_service_runtime import CoreAIRuntime
from core.ai_service_settings import CoreEnvironment, CoreSettings, ProviderRouteSettings


def _settings(capability: CapabilityIA) -> CoreSettings:
    return CoreSettings(
        environment=CoreEnvironment.TEST,
        service_key="core-test-key",
        routes=(
            ProviderRouteSettings(
                configuration_id="primary-openai",
                provider="openai",
                model="primary-model",
                capability=capability,
                priority=100,
                price_snapshot_id="price-primary",
                adapter="openai_compatible",
                base_url="https://primary.invalid/v1",
                api_key="primary-secret",
            ),
            ProviderRouteSettings(
                configuration_id="fallback-gemini",
                provider="gemini",
                model="fallback-model",
                capability=capability,
                priority=90,
                price_snapshot_id="price-fallback",
                adapter="gemini",
                base_url="https://gemini.invalid/v1beta",
                api_key="gemini-secret",
            ),
        ),
    ).validate()


def _response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("POST", "https://provider.invalid"),
    )


def test_text_falls_back_from_openai_compatible_to_gemini(monkeypatch):
    calls: list[str] = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if "primary.invalid" in url:
            return _response(503, {"error": "temporary"})
        return _response(
            200,
            {
                "candidates": [{"content": {"parts": [{"text": "resposta gemini"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 4,
                },
            },
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", fake_post)
    metering = MedidorUsoIAEmMemoria()
    runtime = CoreAIRuntime.from_settings(
        _settings(CapabilityIA.ATENDIMENTO_INTERPRETACAO),
        metering=metering,
    )

    result = runtime.generate_text(
        tenant_id="tenant-a",
        unit_id="unit-a",
        request_id="req-text",
        correlation_id="corr-text",
        system_prompt="Responda em português.",
        messages=(TextMessage(role="user", content="Olá"),),
    )

    assert result.content == "resposta gemini"
    assert result.provider == "gemini"
    assert result.fallback_used is True
    assert len(calls) == 2
    assert [event.outcome.value for event in metering.eventos] == [
        "transient_failure",
        "success",
    ]


def test_audio_falls_back_to_gemini_multimodal(monkeypatch):
    calls: list[str] = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if "primary.invalid" in url:
            return _response(429, {"error": "rate-limited"})
        body = kwargs["json"]
        inline_data = body["contents"][0]["parts"][1]["inlineData"]
        assert inline_data["mimeType"] == "audio/ogg"
        assert inline_data["data"]
        return _response(
            200,
            {
                "candidates": [{"content": {"parts": [{"text": "áudio transcrito"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 8,
                    "candidatesTokenCount": 3,
                },
            },
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", fake_post)
    runtime = CoreAIRuntime.from_settings(
        _settings(CapabilityIA.ATENDIMENTO_TRANSCRICAO)
    )

    result = runtime.transcribe_audio(
        tenant_id="tenant-a",
        unit_id="unit-a",
        request_id="req-audio",
        correlation_id="corr-audio",
        audio=b"binary-audio",
        mime_type="audio/ogg",
        instruction="Transcreva o áudio.",
    )

    assert result.content == "áudio transcrito"
    assert result.provider == "gemini"
    assert result.fallback_used is True
    assert len(calls) == 2
