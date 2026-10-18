from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import (
    AIControlPlaneStore,
    ControlPlaneBase,
    RouteDefinition,
)
from core.ai_control_plane_runtime import (
    CoreControlPlaneAIRuntime,
    FMManagedCredentialResolver,
)
from core.ai_router import CapabilityIA, FalhaRotaDefinitiva, MedidorUsoIAEmMemoria
from core.ai_service_contracts import TextMessage
from core.seguranca.segredos import ReferenceSecretStore, SecretValue


class Resolver:
    def __init__(self):
        self.calls = []

    def resolve_for_request(
        self, *, tenant_id, unit_id, capability, credential_source, secret_reference
    ):
        assert unit_id == "unit-1"
        assert capability == "atendimento_interpretacao"
        return self.resolve(
            tenant_id=tenant_id,
            credential_source=credential_source,
            secret_reference=secret_reference,
        )

    def resolve(self, *, tenant_id, credential_source, secret_reference):
        self.calls.append((tenant_id, credential_source, secret_reference))
        if credential_source == "tenant_managed":
            assert secret_reference.startswith(f"integration:{tenant_id}:")
            return SecretValue("tenant-secret")
        return SecretValue("fm-secret")


def _plane():
    engine = create_engine("sqlite://")
    ControlPlaneBase.metadata.create_all(engine)
    store = AIControlPlaneStore(sessionmaker(engine, expire_on_commit=False))
    store.register_provider(
        provider_id="openai", adapter="openai_compatible", base_url="https://provider.invalid/v1"
    )
    store.register_model(model_id="text-model", provider_id="openai", name="example")
    store.grant_capability(
        model_id="text-model", capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO
    )
    store.set_provider_health(provider_id="openai", status="healthy", circuit="closed")
    return store


def _policy(*, identifier, scope, tenant=None, credential_source="fm_managed"):
    ref = (
        f"integration:{tenant}:credential-1"
        if credential_source == "tenant_managed"
        else "env:FM_PROVIDER_KEY"
    )
    return RouteDefinition(
        policy_id=identifier,
        scope=scope,
        tenant_id=tenant,
        unit_id=None,
        model_id="text-model",
        capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        priority=100,
        price_snapshot_id=identifier + "-price",
        credential_source=credential_source,
        secret_reference=ref,
    )


def _generate(runtime, tenant):
    return runtime.generate_text(
        tenant_id=tenant,
        unit_id="unit-1",
        request_id="req-" + tenant,
        correlation_id="corr-" + tenant,
        system_prompt="Responda.",
        messages=(TextMessage(role="user", content="Oi"),),
    )


def test_runtime_uses_new_scoped_policy_without_restart(monkeypatch):
    store = _plane()
    store.add_route(_policy(identifier="platform", scope="platform"))
    metering = MedidorUsoIAEmMemoria()
    resolver = Resolver()
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=resolver, metering=metering
    )
    seen = []

    def post(url, **kwargs):
        seen.append((url, kwargs["headers"]["Authorization"]))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "resposta"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", post)
    before = _generate(runtime, "tenant-a")
    assert before.price_snapshot_id == "platform-price"
    store.add_route(
        _policy(
            identifier="tenant-a-policy",
            scope="tenant",
            tenant="tenant-a",
            credential_source="tenant_managed",
        )
    )
    after = _generate(runtime, "tenant-a")
    other = _generate(runtime, "tenant-b")
    assert after.price_snapshot_id == "tenant-a-policy-price"
    assert other.price_snapshot_id == "platform-price"
    assert [token for _, token in seen] == [
        "Bearer fm-secret",
        "Bearer tenant-secret",
        "Bearer fm-secret",
    ]
    assert resolver.calls[1][0] == "tenant-a"
    assert [event.tenant_id for event in metering.eventos] == [
        "tenant-a",
        "tenant-a",
        "tenant-b",
    ]


def test_default_resolver_refuses_byok_before_provider_call(monkeypatch):
    store = _plane()
    store.add_route(
        _policy(
            identifier="tenant",
            scope="tenant",
            tenant="tenant-a",
            credential_source="tenant_managed",
        )
    )
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store,
        credentials=FMManagedCredentialResolver(ReferenceSecretStore(mapping={})),
    )
    called = []
    monkeypatch.setattr("core.ai_providers.httpx.post", lambda *a, **kw: called.append(a))
    with pytest.raises(FalhaRotaDefinitiva, match="core_ai_credential_unavailable"):
        _generate(runtime, "tenant-a")
    assert called == []


def test_provider_secret_cannot_leak_through_settings_repr():
    from core.ai_service_settings import ProviderRouteSettings

    route = ProviderRouteSettings(
        configuration_id="p",
        provider="openai",
        model="example",
        capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        priority=10,
        price_snapshot_id="snapshot",
        adapter="openai_compatible",
        base_url="https://provider.invalid",
        api_key="sensitive-value",
    )
    assert "sensitive-value" not in repr(route)


def test_primary_route_succeeds_even_if_fallback_secret_is_unavailable(monkeypatch):
    from dataclasses import replace

    store = _plane()
    store.add_route(_policy(identifier="primary", scope="platform"))
    store.add_route(replace(
        _policy(identifier="fallback", scope="platform"),
        priority=90,
        secret_reference="env:FM_F3_SECRET_NOT_AVAILABLE",
    ))
    # Both routes share provider/model but have distinct credentials.
    # A successful primary request must not resolve the fallback credential.
    monkeypatch.setenv("FM_PROVIDER_KEY", "primary-test-secret")
    monkeypatch.delenv("FM_F3_SECRET_NOT_AVAILABLE", raising=False)

    seen = []

    def fake_post(url, **kwargs):
        seen.append(kwargs["headers"]["Authorization"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", fake_post)
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store,
        credentials=FMManagedCredentialResolver(ReferenceSecretStore()),
    )
    result = _generate(runtime, "tenant-a")
    assert result.content == "ok"
    assert result.fallback_used is False
    assert seen == ["Bearer primary-test-secret"]
