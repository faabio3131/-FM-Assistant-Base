"""Provider-facing completion caps for configurable plan/token policies."""
from __future__ import annotations

import httpx
import pytest

from core.ai_providers import GeminiExecutor, OpenAICompatibleExecutor
from core.ai_router import CapabilityIA, RotaIA, SolicitacaoIA
from core.ai_service_contracts import TextMessage, TextRequestContent
from core.ai_service_settings import ProviderRouteSettings


def settings(*, adapter="openai_compatible", ceiling=128):
    return ProviderRouteSettings(
        configuration_id="test-route", provider="gemini" if adapter == "gemini" else "openai",
        model="test-model", capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        priority=1, price_snapshot_id="test-price", adapter=adapter,
        base_url="https://example.invalid/v1", api_key="synthetic-only",
        max_output_tokens=ceiling,
    )


def request():
    return SolicitacaoIA(
        tenant_id="tenant-1", unidade_id="unit-1",
        request_id="request-1", correlation_id="correlation-1",
        capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        conteudo=TextRequestContent(
            system_prompt="Synthetic", messages=(TextMessage(role="user", content="Hi"),),
        ),
    )


def route(s):
    return RotaIA(
        configuracao_id=s.configuration_id, provider=s.provider,
        model=s.model, capability=s.capability, prioridade=s.priority,
        price_snapshot_id=s.price_snapshot_id,
    )


def test_openai_compatible_completion_ceiling_sent_before_provider(monkeypatch):
    data = []

    def fake_post(url, **kwargs):
        data.append(kwargs["json"])
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", fake_post)
    cfg = settings()
    assert OpenAICompatibleExecutor(cfg).executar(
        rota=route(cfg), solicitacao=request(),
    ).conteudo == "ok"
    assert data[0]["max_tokens"] == 128
    assert data[0]["model"] == "test-model"


def test_gemini_completion_ceiling_sent_before_provider(monkeypatch):
    data = []

    def fake_post(url, **kwargs):
        data.append(kwargs["json"])
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", fake_post)
    cfg = settings(adapter="gemini", ceiling=350)
    assert GeminiExecutor(cfg).executar(
        rota=route(cfg), solicitacao=request(),
    ).conteudo == "ok"
    assert data[0]["generationConfig"]["maxOutputTokens"] == 350


@pytest.mark.parametrize("invalid", [0, -1, 1_000_001, True, "128", 2.3])
def test_output_token_policy_rejects_invalid_ceiling(invalid):
    with pytest.raises(ValueError, match="core_ai_output_ceiling_invalid"):
        settings(ceiling=invalid)
