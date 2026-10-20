"""Executores concretos de providers para o AIModelRouter."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

import httpx

from core.ai_router import (
    ConteudoAudioIA,
    ExecutorModeloIA,
    FalhaRotaDefinitiva,
    FalhaRotaTransitoria,
    RespostaModeloIA,
    RotaIA,
    SolicitacaoIA,
)
from core.ai_service_contracts import TextRequestContent
from core.ai_service_settings import ProviderRouteSettings

_TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


def _status_guard(response: httpx.Response, *, provider: str) -> None:
    if response.status_code in _TRANSIENT_STATUS:
        raise FalhaRotaTransitoria(f"ai_provider.{provider}.transient_http")
    if not 200 <= response.status_code < 300:
        raise FalhaRotaDefinitiva(f"ai_provider.{provider}.definitive_http")


def _json(response: httpx.Response, *, provider: str) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise FalhaRotaDefinitiva(f"ai_provider.{provider}.invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise FalhaRotaDefinitiva(f"ai_provider.{provider}.invalid_payload")
    return payload


class OpenAICompatibleExecutor:
    def __init__(self, settings: ProviderRouteSettings) -> None:
        self._settings = settings

    def executar(self, *, rota: RotaIA, solicitacao: SolicitacaoIA) -> RespostaModeloIA:
        try:
            if isinstance(solicitacao.conteudo, ConteudoAudioIA):
                return self._audio(rota=rota, content=solicitacao.conteudo)
            if isinstance(solicitacao.conteudo, TextRequestContent):
                return self._text(rota=rota, content=solicitacao.conteudo)
        except httpx.RequestError as exc:
            raise FalhaRotaTransitoria("ai_provider.openai_compatible.network") from exc
        raise FalhaRotaDefinitiva("ai_provider.openai_compatible.unsupported_content")

    def _text(self, *, rota: RotaIA, content: TextRequestContent) -> RespostaModeloIA:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": content.system_prompt.strip()}
        ]
        messages.extend({"role": item.role, "content": item.content} for item in content.messages)
        body: dict[str, Any] = {
            "model": rota.model, "messages": messages, "temperature": 0.2,
        }
        if self._settings.max_output_tokens is not None:
            body["max_tokens"] = self._settings.max_output_tokens
        response = httpx.post(
            self._settings.base_url + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self._settings.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self._settings.timeout_seconds,
        )
        _status_guard(response, provider="openai_compatible")
        payload = _json(response, provider="openai_compatible")
        try:
            text = str(payload["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise FalhaRotaDefinitiva("ai_provider.openai_compatible.invalid_response") from exc
        if not text:
            raise FalhaRotaDefinitiva("ai_provider.openai_compatible.empty_response")
        usage = payload.get("usage")
        usage = usage if isinstance(usage, Mapping) else {}
        return RespostaModeloIA(
            conteudo=text,
            input_tokens=_int_or_none(usage.get("prompt_tokens")),
            output_tokens=_int_or_none(usage.get("completion_tokens")),
            cached_tokens=_cached_tokens(usage),
        )

    def _audio(self, *, rota: RotaIA, content: ConteudoAudioIA) -> RespostaModeloIA:
        response = httpx.post(
            self._settings.base_url + "/audio/transcriptions",
            headers={"Authorization": f"Bearer {self._settings.api_key}"},
            data={"model": rota.model, "prompt": content.instrucao},
            files={"file": ("audio", content.audio, content.mime_type)},
            timeout=self._settings.timeout_seconds,
        )
        _status_guard(response, provider="openai_compatible")
        payload = _json(response, provider="openai_compatible")
        text = str(payload.get("text", "")).strip()
        if not text:
            raise FalhaRotaDefinitiva("ai_provider.openai_compatible.empty_transcription")
        usage = payload.get("usage")
        usage = usage if isinstance(usage, Mapping) else {}
        return RespostaModeloIA(
            conteudo=text,
            input_tokens=_int_or_none(usage.get("input_tokens")),
            output_tokens=_int_or_none(usage.get("output_tokens")),
            cached_tokens=None,
        )


class GeminiExecutor:
    def __init__(self, settings: ProviderRouteSettings) -> None:
        self._settings = settings

    def executar(self, *, rota: RotaIA, solicitacao: SolicitacaoIA) -> RespostaModeloIA:
        try:
            if isinstance(solicitacao.conteudo, ConteudoAudioIA):
                body = self._audio_body(
                    solicitacao.conteudo,
                    max_output_tokens=self._settings.max_output_tokens,
                )
            elif isinstance(solicitacao.conteudo, TextRequestContent):
                body = self._text_body(
                    solicitacao.conteudo,
                    max_output_tokens=self._settings.max_output_tokens,
                )
            else:
                raise FalhaRotaDefinitiva("ai_provider.gemini.unsupported_content")

            response = httpx.post(
                f"{self._settings.base_url}/models/{rota.model}:generateContent",
                params={"key": self._settings.api_key},
                headers={"Content-Type": "application/json"},
                json=body,
                timeout=self._settings.timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise FalhaRotaTransitoria("ai_provider.gemini.network") from exc

        _status_guard(response, provider="gemini")
        payload = _json(response, provider="gemini")
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text", "")) for part in parts).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise FalhaRotaDefinitiva("ai_provider.gemini.invalid_response") from exc
        if not text:
            raise FalhaRotaDefinitiva("ai_provider.gemini.empty_response")

        usage = payload.get("usageMetadata")
        usage = usage if isinstance(usage, Mapping) else {}
        return RespostaModeloIA(
            conteudo=text,
            input_tokens=_int_or_none(usage.get("promptTokenCount")),
            output_tokens=_int_or_none(usage.get("candidatesTokenCount")),
            cached_tokens=_int_or_none(usage.get("cachedContentTokenCount")),
        )

    @staticmethod
    def _text_body(
        content: TextRequestContent, *, max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        contents = [
            {
                "role": "model" if item.role == "assistant" else "user",
                "parts": [{"text": item.content}],
            }
            for item in content.messages
        ]
        generation_config: dict[str, Any] = {"temperature": 0.2}
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
        return {
            "systemInstruction": {"parts": [{"text": content.system_prompt}]},
            "contents": contents,
            "generationConfig": generation_config,
        }

    @staticmethod
    def _audio_body(
        content: ConteudoAudioIA, *, max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        result = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": content.instrucao},
                        {
                            "inlineData": {
                                "mimeType": content.mime_type,
                                "data": base64.b64encode(content.audio).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.0},
        }
        if max_output_tokens is not None:
            result["generationConfig"]["maxOutputTokens"] = max_output_tokens
        return result


class CompositeAIExecutor(ExecutorModeloIA):
    def __init__(self, settings: tuple[ProviderRouteSettings, ...]) -> None:
        executors: dict[str, ExecutorModeloIA] = {}
        for route in settings:
            if route.adapter == "openai_compatible":
                executor: ExecutorModeloIA = OpenAICompatibleExecutor(route)
            elif route.adapter == "gemini":
                executor = GeminiExecutor(route)
            else:
                raise ValueError("core_ai_adapter_invalid")
            executors[route.configuration_id] = executor
        self._executors = executors

    def executar(self, *, rota: RotaIA, solicitacao: SolicitacaoIA) -> RespostaModeloIA:
        executor = self._executors.get(rota.configuracao_id)
        if executor is None:
            raise FalhaRotaDefinitiva("ai_provider.executor_missing")
        return executor.executar(rota=rota, solicitacao=solicitacao)


def _int_or_none(value: Any) -> int | None:
    """Only exact, nonnegative provider usage counts are auditable.

    int(True), int(1.9), whitespace and scientific notation previously
    truncated/coerced inconsistent provider receipts. Unknown metering must
    retain the Core reservation; it can never silently become billable 0/1.
    """
    if type(value) is int:
        return value if 0 <= value <= 2_000_000_000 else None
    if (
        isinstance(value, str)
        and 1 <= len(value) <= 10 and value.isascii()
        and value.isdecimal()
    ):
        parsed = int(value)
        return parsed if parsed <= 2_000_000_000 else None
    return None


def _cached_tokens(usage: Mapping[str, Any]) -> int | None:
    details = usage.get("prompt_tokens_details")
    if isinstance(details, Mapping):
        return _int_or_none(details.get("cached_tokens"))
    return None
