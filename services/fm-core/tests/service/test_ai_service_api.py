from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from core.ai_router import CapabilityIA
from core.ai_service_api import create_app
from core.ai_service_contracts import CoreAIResult
from core.ai_service_settings import CoreEnvironment, CoreSettings, ProviderRouteSettings


class FakeRuntime:
    def generate_text(self, **kwargs):
        assert kwargs["tenant_id"] == "tenant-a"
        return CoreAIResult(
            content="resposta do core",
            provider="fake",
            model="fake-model",
            fallback_used=False,
            fallback_reason=None,
            price_snapshot_id="fake-price",
        )

    def transcribe_audio(self, **kwargs):
        assert kwargs["audio"] == b"audio"
        return CoreAIResult(
            content="texto transcrito",
            provider="fake",
            model="fake-audio",
            fallback_used=False,
            fallback_reason=None,
            price_snapshot_id="fake-audio-price",
        )


def _settings() -> CoreSettings:
    return CoreSettings(
        environment=CoreEnvironment.TEST,
        service_key="core-test-key",
        routes=(
            ProviderRouteSettings(
                configuration_id="fake",
                provider="fake",
                model="fake-model",
                capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
                priority=100,
                price_snapshot_id="fake-price",
                adapter="openai_compatible",
                base_url="https://example.invalid/v1",
                api_key="secret",
            ),
        ),
    ).validate()


def test_core_api_requires_internal_service_key():
    app = create_app(_settings(), runtime=FakeRuntime())
    with TestClient(app) as client:
        denied = client.post(
            "/v1/ai/text",
            json={
                "tenant_id": "tenant-a",
                "unit_id": "unit-a",
                "request_id": "req-1",
                "correlation_id": "corr-1",
                "system_prompt": "Você é um assistente.",
                "messages": [{"role": "user", "content": "Olá"}],
            },
        )
        assert denied.status_code == 401


def test_core_api_serves_text_and_audio():
    app = create_app(_settings(), runtime=FakeRuntime())
    headers = {"X-Core-Service-Key": "core-test-key"}

    with TestClient(app) as client:
        text = client.post(
            "/v1/ai/text",
            headers=headers,
            json={
                "tenant_id": "tenant-a",
                "unit_id": "unit-a",
                "request_id": "req-1",
                "correlation_id": "corr-1",
                "system_prompt": "Você é um assistente.",
                "messages": [{"role": "user", "content": "Olá"}],
            },
        )
        assert text.status_code == 200
        assert text.json()["content"] == "resposta do core"

        audio = client.post(
            "/v1/ai/transcribe",
            headers=headers,
            json={
                "tenant_id": "tenant-a",
                "unit_id": "unit-a",
                "request_id": "req-2",
                "correlation_id": "corr-2",
                "mime_type": "audio/ogg",
                "audio_base64": base64.b64encode(b"audio").decode(),
                "instruction": "Transcreva em pt-BR.",
            },
        )
        assert audio.status_code == 200
        assert audio.json()["content"] == "texto transcrito"


def test_audio_quota_denial_is_controlled_and_unauthenticated_calls_never_run():
    from core.ai_quota_store import QuotaDenied

    class DeniedAudio(FakeRuntime):
        attempts = 0

        def transcribe_audio(self, **kwargs):
            self.attempts += 1
            raise QuotaDenied("core_plan.license_unavailable")

    runtime = DeniedAudio()
    app = create_app(_settings(), runtime=runtime)
    body = {
        "tenant_id": "tenant-a", "unit_id": "unit-a",
        "request_id": "deny-audio", "correlation_id": "deny-audio",
        "mime_type": "audio/ogg",
        "audio_base64": base64.b64encode(b"audio").decode(),
        "instruction": "Transcreva em pt-BR.",
    }
    with TestClient(app) as client:
        denied = client.post("/v1/ai/transcribe", json=body)
        assert denied.status_code == 401
        assert runtime.attempts == 0

        blocked = client.post(
            "/v1/ai/transcribe",
            headers={"X-Core-Service-Key": "core-test-key"},
            json=body,
        )
        assert blocked.status_code == 503
        assert blocked.json() == {
            "detail": "core_control_plane_dependency_unavailable",
        }
        assert runtime.attempts == 1
