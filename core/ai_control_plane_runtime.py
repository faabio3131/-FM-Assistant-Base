"""Adaptador F3 para conectar o Control Plane persistente ao AIModelRouter existente.

Nao possui estado de tenant entre requests. Cada request resolve politicas e
referencias atuais no momento da execucao. Nenhum segredo e persistido aqui.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from core.ai_circuit_breaker import CircuitDenied, CircuitOutcome
from core.ai_circuit_state_store import PersistentCircuit
from core.ai_control_plane import AIControlPlaneStore, ControlPlaneError, ResolvedCoreRoute
from core.ai_plan_usage_guard import PlanUsageGuard
from core.ai_providers import GeminiExecutor, OpenAICompatibleExecutor
from core.ai_quota_store import QuotaDenied, QuotaReservations
from core.ai_router import (
    AIModelRouter,
    AIUsageEvent,
    CapabilityIA,
    ConteudoAudioIA,
    ExecutorModeloIA,
    FalhaRotaDefinitiva,
    FalhaRotaTransitoria,
    MedidorUsoIA,
    MedidorUsoIAEmMemoria,
    RespostaModeloIA,
    RotaIA,
    SolicitacaoIA,
)
from core.ai_service_contracts import CoreAIResult, TextMessage, TextRequestContent
from core.ai_service_runtime import _result
from core.ai_service_settings import ProviderRouteSettings
from core.ai_tenant_credential_resolver import TenantCredentialDenied
from core.seguranca.erros import ReferenciaSegredoInvalida, SegredoAusente
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


class ScopedCoreExecutor(ExecutorModeloIA):
    """Resolve credentials only for the actually attempted route."""

    def __init__(
        self, *, routes: tuple[ResolvedCoreRoute, ...], credentials: CoreCredentialResolver,
        circuit: PersistentCircuit | None = None,
        output_token_cap: int | None = None,
    ) -> None:
        self._output_token_cap = output_token_cap
        self._routes = {route.route.configuracao_id: route for route in routes}
        self._credentials = credentials
        self._circuit = circuit

    def executar(self, *, rota: RotaIA, solicitacao: SolicitacaoIA) -> RespostaModeloIA:
        item = self._routes.get(rota.configuracao_id)
        if item is None:
            raise FalhaRotaDefinitiva("ai_provider.executor_missing")
        # Verify circuit scope before resolving any BYOK secret.
        if self._circuit is not None and item.credential_source != "fm_managed":
            raise FalhaRotaDefinitiva("core_circuit.byok_partition_required")
        try:
            if item.credential_source == "tenant_managed":
                scoped = getattr(self._credentials, "resolve_for_request", None)
                if scoped is None:
                    raise TenantCredentialDenied(
                        "core_control_plane.byok_scope_required"
                    )
                secret = scoped(
                    tenant_id=solicitacao.tenant_id,
                    unit_id=solicitacao.unidade_id,
                    capability=solicitacao.capability.value,
                    credential_source=item.credential_source,
                    secret_reference=item.secret_reference,
                )
            else:
                secret = self._credentials.resolve(
                    tenant_id=solicitacao.tenant_id,
                    credential_source=item.credential_source,
                    secret_reference=item.secret_reference,
                )
        except TenantCredentialDenied as exc:
            # A negacao BYOK nunca deve disparar fallback para uma rota FM-managed.
            raise FalhaRotaDefinitiva("core_ai_credential_unavailable") from exc
        except (ControlPlaneError, ReferenciaSegredoInvalida, SegredoAusente) as exc:
            raise FalhaRotaTransitoria("core_ai_credential_unavailable") from exc

        settings = ProviderRouteSettings(
            configuration_id=rota.configuracao_id,
            provider=rota.provider,
            model=rota.model,
            capability=rota.capability,
            priority=rota.prioridade,
            price_snapshot_id=rota.price_snapshot_id,
            adapter=item.adapter,
            base_url=item.base_url,
            api_key=secret.reveal(),
            timeout_seconds=item.timeout_seconds,
            max_output_tokens=self._output_token_cap,
        )
        if item.adapter not in {"gemini", "openai_compatible"}:
            raise FalhaRotaDefinitiva("core_ai_adapter_invalid")
        lease: str | None = None
        version = 0
        if self._circuit is not None:
            # Provider-wide health cannot safely represent independent BYOK
            # credential health; reject until credential-partitioned fencing exists.
            try:
                lease, version = self._circuit.claim(
                    provider_id=rota.provider, now=datetime.now(UTC),
                )
            except CircuitDenied as exc:
                # Never fall back implicitly across credentials on circuit denial.
                raise FalhaRotaDefinitiva("core_circuit.unavailable") from exc
        try:
            executor = (
                GeminiExecutor(settings) if item.adapter == "gemini"
                else OpenAICompatibleExecutor(settings)
            )
            response = executor.executar(rota=rota, solicitacao=solicitacao)
        except FalhaRotaTransitoria:
            if self._circuit is not None:
                self._circuit.finish(
                    provider_id=rota.provider, now=datetime.now(UTC),
                    outcome=CircuitOutcome.TRANSIENT_FAILURE,
                    probe_id=lease, version=version,
                )
            raise
        except FalhaRotaDefinitiva:
            if self._circuit is not None:
                self._circuit.finish(
                    provider_id=rota.provider, now=datetime.now(UTC),
                    outcome=CircuitOutcome.DEFINITIVE_FAILURE,
                    probe_id=lease, version=version,
                )
            raise
        # An unknown/ambiguous executor exception conservatively leaves any
        # half-open probe leased until timeout and requires explicit recovery.
        if self._circuit is not None:
            self._circuit.finish(
                provider_id=rota.provider, now=datetime.now(UTC),
                outcome=CircuitOutcome.SUCCESS, probe_id=lease, version=version,
            )
        return response


class _ScopedMetering(MedidorUsoIA):
    """Per-request usage capture with the persistent meter remaining canonical."""

    def __init__(self, inner: MedidorUsoIA, captured: list[AIUsageEvent]) -> None:
        self._inner = inner
        self._captured = captured

    def registrar(self, evento: AIUsageEvent) -> None:
        self._inner.registrar(evento)
        self._captured.append(evento)


class CoreControlPlaneAIRuntime:
    """Mantem os contratos da API sem duplicar o motor de roteamento."""

    def __init__(
        self,
        *,
        control_plane: AIControlPlaneStore,
        credentials: CoreCredentialResolver,
        metering: MedidorUsoIA | None = None,
        quota: QuotaReservations | None = None,
        circuit: PersistentCircuit | None = None,
        plan_usage: PlanUsageGuard | None = None,
    ) -> None:
        if quota is not None and plan_usage is not None:
            raise ValueError("core_plan.ambiguous_quota_guards")
        self._quota = quota
        self._plan_usage = plan_usage
        self._circuit = circuit
        self._control_plane = control_plane
        self._credentials = credentials
        self._metering = metering or MedidorUsoIAEmMemoria()

    def _router(
        self, *, tenant_id: str, unit_id: str, capability: CapabilityIA,
        capture: list[AIUsageEvent] | None = None,
        output_token_cap: int | None = None,
        attempt_budget: int | None = None,
    ) -> AIModelRouter:
        resolved = self._control_plane.resolve(
            tenant_id=tenant_id, unit_id=unit_id, capability=capability
        )
        sources = {route.credential_source for route in resolved}
        if "tenant_managed" in sources and "fm_managed" in sources:
            raise ControlPlaneError("core_control_plane.mixed_credential_fallback_forbidden")
        return AIModelRouter(
            rotas=tuple(item.route for item in resolved),
            max_attempts=attempt_budget,
            executor=ScopedCoreExecutor(
                routes=resolved, credentials=self._credentials, circuit=self._circuit,
                output_token_cap=output_token_cap,
            ),
            metering=(
                _ScopedMetering(self._metering, capture)
                if capture is not None else self._metering
            ),
        )

    def _execute_guarded(
        self, router_factory: Callable[[int | None, int | None], AIModelRouter],
        request: SolicitacaoIA, capture: list[AIUsageEvent] | None = None,
    ):
        """Opt-in per-request quota admission before ANY provider attempt.

        One request unit is reserved for the entire router/fallback chain.
        On unknown outcome do not refund or retry automatically.
        """
        policy = None
        attempt_budget = None
        if self._plan_usage is not None:
            # Resolve only trusted route metadata; provider credentials are not
            # touched until the full fallback exposure is reserved.
            available = self._control_plane.resolve(
                tenant_id=request.tenant_id, unit_id=request.unidade_id,
                capability=request.capability,
            )
            attempt_budget = len(available)
            if not 1 <= attempt_budget <= 8:
                raise QuotaDenied("core_plan.attempt_budget_invalid")
            policy = self._plan_usage.admit(
                request=request, at=datetime.now(UTC),
                attempt_budget=attempt_budget,
            )
        if self._quota is not None:
            self._quota.reserve(
                tenant_id=request.tenant_id,
                unit_id=request.unidade_id,
                capability=request.capability.value,
                request_id=request.request_id,
                units=1,
                at=datetime.now(UTC),
                for_execution=True,
            )
        if policy is not None and isinstance(request.conteudo, TextRequestContent):
            # Conservative byte-envelope preflight, not a provider tokenizer.
            # Reject oversized prompts before credentials or paid API traffic.
            prompt = request.conteudo.system_prompt
            prompt_bytes = len(prompt.encode("utf-8"))
            for message in request.conteudo.messages:
                prompt_bytes += len(message.content.encode("utf-8"))
                prompt_bytes += len(message.role.encode("utf-8"))
            if prompt_bytes > policy.input_bound:
                raise QuotaDenied("core_plan.input_envelope_exceeded")
        # Construct per-request executor only after quota admission and inject
        # the licensed provider-level output ceiling (OpenAI/Gemini).
        router = router_factory(
            policy.output_bound if policy is not None else None,
            attempt_budget,
        )
        result = router.executar(request)
        if self._plan_usage is not None and policy is not None:
            self._plan_usage.reconcile(
                request=request, policy=policy,
                events=tuple(capture or ()),
            )
        if self._quota is not None:
            self._quota.settle(
                tenant_id=request.tenant_id,
                unit_id=request.unidade_id,
                capability=request.capability.value,
                request_id=request.request_id,
                consumed_units=1,
            )
        return result

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
        capture: list[AIUsageEvent] | None = [] if self._plan_usage is not None else None
        router_factory = lambda output_cap, attempts: self._router(
            tenant_id=tenant_id,
            unit_id=unit_id,
            capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
            capture=capture,
            output_token_cap=output_cap,
            attempt_budget=attempts,
        )
        return _result(
            self._execute_guarded(
                router_factory,
                SolicitacaoIA(
                    tenant_id=tenant_id,
                    unidade_id=unit_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
                    conteudo=TextRequestContent(
                        system_prompt=system_prompt, messages=messages
                    ),
                ), capture=capture,
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
        capture: list[AIUsageEvent] | None = [] if self._plan_usage is not None else None
        router_factory = lambda output_cap: self._router(
            tenant_id=tenant_id,
            unit_id=unit_id,
            capability=CapabilityIA.ATENDIMENTO_TRANSCRICAO,
            capture=capture,
            output_token_cap=output_cap,
        )
        return _result(
            self._execute_guarded(
                router_factory,
                SolicitacaoIA(
                    tenant_id=tenant_id,
                    unidade_id=unit_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    capability=CapabilityIA.ATENDIMENTO_TRANSCRICAO,
                    conteudo=ConteudoAudioIA(
                        audio=audio, mime_type=mime_type, instrucao=instruction
                    ),
                ), capture=capture,
            )
        )
