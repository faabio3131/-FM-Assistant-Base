"""F3.7: contrato BYOK governado, sem rede/secretos reais."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from core.ai_control_plane import ControlPlaneError, ResolvedCoreRoute
from core.ai_control_plane_runtime import ScopedCoreExecutor
from core.ai_router import (
    AIModelRouter,
    CapabilityIA,
    FalhaRotaDefinitiva,
    MedidorUsoIAEmMemoria,
    OutcomeIA,
    RotaIA,
    SolicitacaoIA,
)
from core.ai_tenant_credential_resolver import (
    GovernedCredentialResolver,
    TenantCredentialDenied,
    parse_tenant_secret_reference,
)
from core.seguranca.segredos import SecretValue


@dataclass
class StubFMResolver:
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    error: Exception | None = None

    def resolve(
        self, *, tenant_id: str, credential_source: str, secret_reference: str
    ) -> SecretValue:
        self.calls.append((tenant_id, credential_source, secret_reference))
        if self.error:
            raise self.error
        return SecretValue("fm-test-secret")


@dataclass
class StubTenantGateway:
    calls: list[tuple[str, str]] = field(default_factory=list)
    secret: SecretValue | None = field(default_factory=lambda: SecretValue("byok-test-secret"))
    error: Exception | None = None

    def resolve_active_secret(
        self, *, tenant_id: str, opaque_reference: str
    ) -> SecretValue:
        self.calls.append((tenant_id, opaque_reference))
        if self.error:
            raise self.error
        return self.secret  # type: ignore[return-value]


def _resolver(fm=None, gateway=None):
    fm = fm or StubFMResolver()
    gateway = gateway or StubTenantGateway()
    return GovernedCredentialResolver(
        fm_credentials=fm, tenant_gateway=gateway
    ), fm, gateway


def test_fm_managed_resolution_does_not_touch_tenant_gateway():
    resolver, fm, tenant = _resolver()
    result = resolver.resolve(
        tenant_id="tenant-a",
        credential_source="fm_managed",
        secret_reference="env:FM_PLATFORM_AI_KEY",
    )
    assert result.reveal() == "fm-test-secret"
    assert fm.calls == [("tenant-a", "fm_managed", "env:FM_PLATFORM_AI_KEY")]
    assert tenant.calls == []


def test_byok_resolution_uses_exact_tenant_and_opaque_reference():
    resolver, fm, tenant = _resolver()
    result = resolver.resolve(
        tenant_id="tenant-a",
        credential_source="tenant_managed",
        secret_reference="integration:tenant-a:active-connection-123",
    )
    assert result.reveal() == "byok-test-secret"
    assert tenant.calls == [("tenant-a", "active-connection-123")]
    assert fm.calls == []


@pytest.mark.parametrize(
    "tenant,ref",
    [
        ("tenant-a", "integration:tenant-b:secret-123"),
        ("tenant-a", "integration:tenant-a"),
        ("tenant-a", "integration:tenant-a:"),
        ("tenant-a", "integration:tenant-a:secret:extra"),
        ("tenant-a", "integration:tenant-a:../../secret"),
        ("tenant-a", "integration:tenant-a:secret?token=abc"),
        ("tenant-a", "integration:tenant-a: secret"),
        ("tenant-a", "env:PROVIDER_KEY"),
        ("", "integration:tenant-a:secret"),
        ("tenant a", "integration:tenant a:secret"),
        ("tenant-a", "integration:tenant-a:secret\n"),
    ],
)
def test_invalid_reference_is_denied_before_gateway(tenant, ref):
    resolver, fm, gateway = _resolver()
    with pytest.raises(TenantCredentialDenied):
        resolver.resolve(
            tenant_id=tenant,
            credential_source="tenant_managed",
            secret_reference=ref,
        )
    assert gateway.calls == []
    assert fm.calls == []


def test_invalid_origin_never_falls_back_to_other_provider():
    resolver, fm, gateway = _resolver()
    for origin in ("tenant", "", "unknown", "TENANT_MANAGED"):
        with pytest.raises(ControlPlaneError):
            resolver.resolve(
                tenant_id="tenant-a",
                credential_source=origin,
                secret_reference="integration:tenant-a:secret123",
            )
    assert fm.calls == []
    assert gateway.calls == []


def test_byok_denied_or_unavailable_must_not_fallback_to_fm():
    gateway = StubTenantGateway(error=PermissionError("not active"))
    resolver, fm, _ = _resolver(gateway=gateway)
    with pytest.raises(TenantCredentialDenied):
        resolver.resolve(
            tenant_id="tenant-a",
            credential_source="tenant_managed",
            secret_reference="integration:tenant-a:secret123",
        )
    assert fm.calls == []


def test_unexpected_gateway_return_is_denied_without_leaking():
    gateway = StubTenantGateway(secret=None)
    resolver, fm, _ = _resolver(gateway=gateway)
    with pytest.raises(TenantCredentialDenied, match="byok_credential_unavailable"):
        resolver.resolve(
            tenant_id="tenant-a",
            credential_source="tenant_managed",
            secret_reference="integration:tenant-a:secret123",
        )
    assert fm.calls == []


def test_reference_object_repr_hides_opaque_identifier():
    ref = parse_tenant_secret_reference(
        tenant_id="tenant-a",
        secret_reference="integration:tenant-a:highly-sensitive-opaque-ref",
    )
    assert ref.opaque_id == "highly-sensitive-opaque-ref"
    assert "highly-sensitive" not in repr(ref)


def test_fm_secret_cannot_be_obtained_using_tenant_origin():
    resolver, fm, tenant = _resolver()
    with pytest.raises(TenantCredentialDenied):
        resolver.resolve(
            tenant_id="tenant-a",
            credential_source="tenant_managed",
            secret_reference="env:FM_PLATFORM_AI_KEY",
        )
    assert fm.calls == []
    assert tenant.calls == []


def test_byok_authorization_denial_does_not_trigger_fm_route_fallback():
    capability = CapabilityIA.ATENDIMENTO_INTERPRETACAO
    byok_route = RotaIA(
        configuracao_id="byok-priority",
        provider="byok-provider",
        model="model-b",
        capability=capability,
        prioridade=100,
        price_snapshot_id="price-1",
    )
    fm_route = RotaIA(
        configuracao_id="fm-fallback",
        provider="fm-provider",
        model="model-f",
        capability=capability,
        prioridade=50,
        price_snapshot_id="price-2",
    )
    routes = (
        ResolvedCoreRoute(
            route=byok_route,
            scope="tenant",
            adapter="openai_compatible",
            base_url="https://provider.invalid",
            credential_source="tenant_managed",
            secret_reference="integration:tenant-a:disabled-key",
            timeout_seconds=3,
        ),
        ResolvedCoreRoute(
            route=fm_route,
            scope="platform",
            adapter="openai_compatible",
            base_url="https://provider.invalid",
            credential_source="fm_managed",
            secret_reference="env:FM_TEST_KEY",
            timeout_seconds=3,
        ),
    )
    fm = StubFMResolver(error=PermissionError("FM route must never be attempted"))
    gateway = StubTenantGateway(error=PermissionError("revoked tenant credential"))
    resolver, _, _ = _resolver(fm=fm, gateway=gateway)
    metering = MedidorUsoIAEmMemoria()
    router = AIModelRouter(
        rotas=(byok_route, fm_route),
        executor=ScopedCoreExecutor(routes=routes, credentials=resolver),
        metering=metering,
    )
    request = SolicitacaoIA(
        tenant_id="tenant-a",
        unidade_id="unit-a",
        request_id="request-1",
        correlation_id="correlation-1",
        capability=capability,
        conteudo=object(),
    )
    with pytest.raises(FalhaRotaDefinitiva, match="core_ai_credential_unavailable"):
        router.executar(request)
    assert gateway.calls == [("tenant-a", "disabled-key")]
    assert fm.calls == []
    assert len(metering.eventos) == 1
    assert metering.eventos[0].outcome is OutcomeIA.FALHA_DEFINITIVA
