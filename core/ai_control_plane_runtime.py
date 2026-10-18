"""Adaptador F3 para conectar o Control Plane persistente ao AIModelRouter existente.

Nao possui estado de tenant entre requests. Cada request resolve politicas e
referencias atuais no momento da execucao. Nenhum segredo e persistido aqui.
"""

from __future__ import annotations

from typing import Protocol

from core.ai_control_plane import AIControlPlaneStore, ControlPlaneError
from core.ai_providers import CompositeAIExecutor
from core.ai_router import (
    AIModelRouter,
    CapabilityIA,
    ConteudoAudioIA,
    MedidorUsoIA,
    MedidorUsoIAEmMemoria,
    SolicitacaoIA,
)
from core.ai_service_contracts import CoreAIResult, TextMessage, TextRequestContent
from core.ai_service_runtime import _result
from core.ai_service_settings import ProviderRouteSettings
from core.seguranca.segredos import SecretStore, SecretValue


class CoreCredentialResolver(Protocol):
    def resolve(
        self, *, tenant_id: str, credential_source: str, secret_reference: str
    ) -> SecretValue: ...


class FMManagedCredentialResolver:
    """Resolver restrito a referencias FM. BYOK requer port dedicado e governado."""

    def __init__(self, store: SecretStore) -> None:
        self._store = store

    def resolve(
        self, *, tenant_id: str, credential_source: str, secret_reference: str
    ) -> SecretValue:
        if credential_source != "fm_managed":
            raise ControlPlaneError("core_control_plane.byok_resolver_not_configured")
        if not secret_reference.startswith(("env:", "vault:")):
            raise ControlPlaneError("core_control_plane.invalid_fm_reference")
        return self._store.resolve(secret_reference)


class CoreControlPlaneAIRuntime:
    """Mantem os contratos da API sem duplicar o motor de roteamento."""

    def __init__(
        self,
        *,
        control_plane: AIControlPlaneStore,
        credentials: CoreCredentialResolver,
        metering: MedidorUsoIA | None = None,
    ) -> None:
        self._control_plane = control_plane
        self._credentials = credentials
        self._metering = metering or MedidorUsoIAEmMemoria()

    def _router(
        self, *, tenant_id: str, unit_id: str, capability: CapabilityIA
    ) -> AIModelRouter:
        resolved = self._control_plane.resolve(
            tenant_id=tenant_id, unit_id=unit_id, capability=capability
        )
        settings: list[ProviderRouteSettings] = []
        for item in resolved:
            secret = self._credentials.resolve(
                tenant_id=tenant_id,
                credential_source=item.credential_source,
                secret_reference=item.secret_reference,
            )
            settings.append(
                ProviderRouteSettings(
                    configuration_id=item.route.configuracao_id,
                    provider=item.route.provider,
                    model=item.route.model,
                    capability=capability,
                    priority=item.route.prioridade,
                    price_snapshot_id=item.route.price_snapshot_id,
                    adapter=item.adapter,
                    base_url=item.base_url,
                    api_key=secret.reveal(),
                    timeout_seconds=item.timeout_seconds,
                )
            )
        return AIModelRouter(
            rotas=tuple(item.route for item in resolved),
            executor=CompositeAIExecutor(tuple(settings)),
            metering=self._metering,
        )

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
        router = self._router(
            tenant_id=tenant_id,
            unit_id=unit_id,
            capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        )
        return _result(
            router.executar(
                SolicitacaoIA(
                    tenant_id=tenant_id,
                    unidade_id=unit_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
                    conteudo=TextRequestContent(
                        system_prompt=system_prompt, messages=messages
                    ),
                )
            )
        )

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
        router = self._router(
            tenant_id=tenant_id,
            unit_id=unit_id,
            capability=CapabilityIA.ATENDIMENTO_TRANSCRICAO,
        )
        return _result(
            router.executar(
                SolicitacaoIA(
                    tenant_id=tenant_id,
                    unidade_id=unit_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    capability=CapabilityIA.ATENDIMENTO_TRANSCRICAO,
                    conteudo=ConteudoAudioIA(
                        audio=audio, mime_type=mime_type, instrucao=instruction
                    ),
                )
            )
        )
