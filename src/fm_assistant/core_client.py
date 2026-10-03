"""Cliente interno da Assistente para o FM Core Base."""

from __future__ import annotations

import base64
from uuid import uuid4

import httpx


class CoreAIClient:
    def __init__(
        self,
        *,
        base_url: str,
        service_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        url = base_url.rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise ValueError("core_base_url_invalid")
        if not service_key.strip():
            raise ValueError("core_service_key_required")
        self._base_url = url
        self._service_key = service_key
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "X-Core-Service-Key": self._service_key,
            "Content-Type": "application/json",
        }

    def generate_text(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        system_prompt: str,
        messages: list[dict[str, str]],
        correlation_id: str | None = None,
    ) -> str:
        request_id = str(uuid4())
        corr = correlation_id or request_id
        response = httpx.post(
            self._base_url + "/v1/ai/text",
            headers=self._headers(),
            json={
                "tenant_id": tenant_id,
                "unit_id": unit_id,
                "request_id": request_id,
                "correlation_id": corr,
                "system_prompt": system_prompt,
                "messages": messages,
            },
            timeout=self._timeout,
        )
        self._raise_for_core(response)
        payload = response.json()
        content = str(payload.get("content", "")).strip()
        if not content:
            raise RuntimeError("core_ai_empty_text")
        return content

    def transcribe_audio(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        correlation_id: str,
        content: bytes,
        mime_type: str,
    ) -> str:
        request_id = str(uuid4())
        response = httpx.post(
            self._base_url + "/v1/ai/transcribe",
            headers=self._headers(),
            json={
                "tenant_id": tenant_id,
                "unit_id": unit_id,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "mime_type": mime_type,
                "audio_base64": base64.b64encode(content).decode("ascii"),
                "instruction": (
                    "Transcreva fielmente o áudio para texto no idioma falado. "
                    "Não invente conteúdo ausente."
                ),
            },
            timeout=self._timeout,
        )
        self._raise_for_core(response)
        payload = response.json()
        text = str(payload.get("content", "")).strip()
        if not text:
            raise RuntimeError("core_ai_empty_transcription")
        return text

    @staticmethod
    def _raise_for_core(response: httpx.Response) -> None:
        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError("core_ai_temporarily_unavailable")
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"core_ai_rejected_http_{response.status_code}")


class CoreAudioTranscriber:
    """Adapter da porta de áudio da Assistente para o FM Core Base."""

    def __init__(self, client: CoreAIClient) -> None:
        self._client = client

    def transcribe(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        correlation_id: str,
        content: bytes,
        mime_type: str,
    ) -> str:
        return self._client.transcribe_audio(
            tenant_id=tenant_id,
            unit_id=unit_id,
            correlation_id=correlation_id,
            content=content,
            mime_type=mime_type,
        )
