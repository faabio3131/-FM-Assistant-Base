"""Composition root do serviço multimodelo do FM Core Base."""

from __future__ import annotations

from core.ai_providers import CompositeAIExecutor
from core.ai_router import (
    AIModelRouter,
    CapabilityIA,
    ConteudoAudioIA,
    MedidorUsoIA,
    MedidorUsoIAEmMemoria,
    RotaIA,
    SolicitacaoIA,
)
from core.ai_service_contracts import CoreAIResult, TextMessage, TextRequestContent
from core.ai_service_settings import CoreSettings


class CoreAIRuntime:
    def __init__(self, *, router: AIModelRouter) -> None:
        self._router = router

    @classmethod
    def from_settings(
        cls,
        settings: CoreSettings,
        *,
        metering: MedidorUsoIA | None = None,
    ) -> CoreAIRuntime:
        routes = tuple(
            RotaIA(
                configuracao_id=item.configuration_id,
                provider=item.provider,
                model=item.model,
                capability=item.capability,
                prioridade=item.priority,
                price_snapshot_id=item.price_snapshot_id,
            )
            for item in settings.routes
        )
        router = AIModelRouter(
            rotas=routes,
            executor=CompositeAIExecutor(settings.routes),
            metering=metering or MedidorUsoIAEmMemoria(),
        )
        return cls(router=router)

    def generate_text(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        request_id: str,
        correlation_id: str,
        system_prompt: str,
        messages: tuple[TextMessage, ...],
    ) -> CoreAIResult:
        result = self._router.executar(
            SolicitacaoIA(
                tenant_id=tenant_id,
                unidade_id=unit_id,
                request_id=request_id,
                correlation_id=correlation_id,
                capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
                conteudo=TextRequestContent(
                    system_prompt=system_prompt,
                    messages=messages,
                ),
            )
        )
        return _result(result)

    def transcribe_audio(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        request_id: str,
        correlation_id: str,
        audio: bytes,
        mime_type: str,
        instruction: str,
    ) -> CoreAIResult:
        result = self._router.executar(
            SolicitacaoIA(
                tenant_id=tenant_id,
                unidade_id=unit_id,
                request_id=request_id,
                correlation_id=correlation_id,
                capability=CapabilityIA.ATENDIMENTO_TRANSCRICAO,
                conteudo=ConteudoAudioIA(
                    audio=audio,
                    mime_type=mime_type,
                    instrucao=instruction,
                ),
            )
        )
        return _result(result)


def _result(result) -> CoreAIResult:
    text = str(result.conteudo).strip()
    if not text:
        raise RuntimeError("core_ai_empty_result")
    return CoreAIResult(
        content=text,
        provider=result.provider,
        model=result.model,
        fallback_used=result.fallback_used,
        fallback_reason=result.fallback_reason,
        price_snapshot_id=result.price_snapshot_id,
    )
