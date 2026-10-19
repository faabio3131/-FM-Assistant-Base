from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import (
    AIControlPlaneStore,
    ControlPlaneBase,
    ControlPlaneError,
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


def test_mixed_byok_fm_fallback_fails_closed_before_provider(monkeypatch):
    from dataclasses import replace

    store = _plane()
    store.add_route(_policy(
        identifier="tenant-byok", scope="tenant", tenant="tenant-a",
        credential_source="tenant_managed",
    ))
    store.add_route(replace(
        _policy(identifier="tenant-fm", scope="tenant", tenant="tenant-a"),
        priority=90,
    ))
    requests = []
    monkeypatch.setattr(
        "core.ai_providers.httpx.post",
        lambda *a, **kw: requests.append(kw),
    )
    resolver = Resolver()
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=resolver,
    )
    with pytest.raises(ControlPlaneError, match="mixed_credential_fallback_forbidden"):
        _generate(runtime, "tenant-a")
    assert requests == []
    assert resolver.calls == []


def test_signed_plan_output_cap_is_applied_to_provider_after_admission(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from core.ai_plan_usage_guard import PlanQuotaPolicy, PlanUsageGuard
    from core.ai_quota_store import QuotaReservations

    store = _plane()
    store.add_route(_policy(identifier="plan-bounded", scope="platform"))
    ledger = QuotaReservations(store._sessions)

    class SignedAuthority:
        def resolve(self, *, tenant_id, unit_id, capability, now):
            return PlanQuotaPolicy(
                tenant_id=tenant_id, unit_id=unit_id,
                plan_code="ALL_FEATURES", revision=7,
                valid_until=now + timedelta(seconds=30),
                input_bound=64, output_bound=17,
                scopes=(("ai.requests", "tenant"),
                        ("ai.total_tokens", "tenant")),
                grants=(("ai.requests", "tenant", 2, 86400),
                        ("ai.total_tokens", "tenant", 100, 86400)),
            )

    seen = []

    def provider(url, **kwargs):
        seen.append(kwargs["json"]["max_tokens"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {
                    "prompt_tokens": 10, "completion_tokens": 5,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("core.ai_providers.httpx.post", provider)
    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=Resolver(),
        plan_usage=PlanUsageGuard(quota=ledger, authority=SignedAuthority()),
    )
    result = _generate(runtime, "tenant-a")
    assert result.content == "ok"
    assert seen == [17]
    current = ledger.usage_snapshot(
        tenant_id="tenant-a", unit_id="__tenant__",
        capability="ai.total_tokens", at=datetime.now(UTC),
    )
    assert current.policy_revision == 7
    assert current.consumed_units == 15
    assert current.reserved_units == 0


def test_revoked_license_never_contacts_model_or_resolves_credentials(monkeypatch):
    from datetime import timedelta

    from core.ai_plan_usage_guard import PlanQuotaPolicy, PlanUsageGuard
    from core.ai_quota_store import QuotaDenied, QuotaReservations

    store = _plane()
    store.add_route(_policy(identifier="revoked", scope="platform"))
    resolver = Resolver()
    attempts = []
    monkeypatch.setattr(
        "core.ai_providers.httpx.post",
        lambda *args, **kwargs: attempts.append((args, kwargs)),
    )

    class RevokedAuthority:
        def resolve(self, *, tenant_id, unit_id, capability, now):
            return PlanQuotaPolicy(
                tenant_id=tenant_id, unit_id=unit_id,
                plan_code="REVOKED", revision=1,
                valid_until=now - timedelta(seconds=1),
                input_bound=100, output_bound=30,
                scopes=(("ai.requests", "tenant"),
                        ("ai.total_tokens", "tenant")),
                grants=(("ai.requests", "tenant", 100, 86400),
                        ("ai.total_tokens", "tenant", 10000, 86400)),
            )

    runtime = CoreControlPlaneAIRuntime(
        control_plane=store, credentials=resolver,
        plan_usage=PlanUsageGuard(
            quota=QuotaReservations(store._sessions),
            authority=RevokedAuthority(),
        ),
    )
    with pytest.raises(QuotaDenied, match="license_unavailable"):
        _generate(runtime, "tenant-a")
    assert resolver.calls == []
    assert attempts == []
