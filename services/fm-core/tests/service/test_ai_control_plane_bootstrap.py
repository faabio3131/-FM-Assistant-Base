from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from core.ai_control_plane import AIControlPlaneStore, ControlPlaneError, RouteDefinition
from core.ai_control_plane_bootstrap import build_persistent_core
from core.ai_pricing import PriceSnapshotIA, TarifaIA
from core.ai_router import CapabilityIA
from core.ai_service_api import create_app
from core.ai_service_settings import CoreEnvironment, CoreSettings
from core.ai_usage_ledger import PersistentAIFinOps
from core.seguranca.segredos import SecretValue


def migrated_db(tmp_path: Path) -> tuple[str, AIControlPlaneStore, PersistentAIFinOps]:
    url = f"sqlite:///{tmp_path / 'core.db'}"
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    return url, AIControlPlaneStore(sessions), PersistentAIFinOps(sessions)


def test_control_plane_app_uses_existing_router_and_persisted_metering(
    tmp_path, monkeypatch
):
    url, store, ledger = migrated_db(tmp_path)
    store.register_provider(
        provider_id="openai", adapter="openai_compatible",
        base_url="https://provider.invalid/v1",
    )
    store.register_model(model_id="model-id", provider_id="openai", name="model-1")
    cap = CapabilityIA.ATENDIMENTO_INTERPRETACAO
    store.grant_capability(model_id="model-id", capability=cap)
    store.set_provider_health(provider_id="openai", status="healthy", circuit="closed")
    store.add_route(RouteDefinition(
        policy_id="route-1", scope="platform", tenant_id=None, unit_id=None,
        model_id="model-id", capability=cap, priority=100,
        price_snapshot_id="price-1", credential_source="fm_managed",
        secret_reference="env:FM_F3_TEST_KEY",
    ))
    ledger.add_price_snapshot(PriceSnapshotIA(
        price_snapshot_id="price-1", provider="openai", model="model-1",
        modalidade="text", moeda="USD", versao=1,
        vigencia_inicio=datetime(2025, 1, 1, tzinfo=UTC),
        vigencia_fim=None,
        tarifas=(
            TarifaIA(componente="input_tokens", preco=Decimal("0.02"), unidades_por_preco=1000),
            TarifaIA(componente="output_tokens", preco=Decimal("0.03"), unidades_por_preco=1000),
        ),
    ))
    monkeypatch.setenv("FM_F3_TEST_KEY", "isolated-test-secret")

    def mock_post(url, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer isolated-test-secret"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "resposta cp"}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
        }, request=httpx.Request("POST", url))
    monkeypatch.setattr("core.ai_providers.httpx.post", mock_post)
    cfg = CoreSettings(
        environment=CoreEnvironment.TEST, service_key="test-key", routes=(),
        control_plane_database_url=url,
    ).validate()
    with TestClient(create_app(cfg)) as client:
        assert client.get("/health").json()["mode"] == "control_plane"
        assert client.get("/ready").status_code == 200
        payload = {
            "tenant_id": "tenant-a", "unit_id": "unit-1",
            "request_id": "req-1", "correlation_id": "corr-1",
            "system_prompt": "Atenda.", "messages": [{"role": "user", "content": "oi"}],
        }
        assert client.post("/v1/ai/text", json=payload).status_code == 401
        reply = client.post("/v1/ai/text", json=payload,
                            headers={"X-Core-Service-Key": "test-key"})
        assert reply.status_code == 200
        assert reply.json()["content"] == "resposta cp"
    buckets = ledger.listar(
        tenant_id="tenant-a", unidade_id="unit-1",
        inicio=datetime(2026, 1, 1).date(), fim=datetime(2027, 1, 1).date(),
    )
    assert len(buckets) == 1
    assert buckets[0].attempts == 1
    assert buckets[0].cost_total == Decimal("0.05")


def test_boot_fails_closed_without_migrations(tmp_path):
    url = f"sqlite:///{tmp_path / 'unmigrated.db'}"
    cfg = CoreSettings(
        environment=CoreEnvironment.TEST, service_key="test-key",
        routes=(), control_plane_database_url=url,
    ).validate()
    with pytest.raises(RuntimeError, match="database_not_ready"), TestClient(create_app(cfg)):
        pass


def test_missing_provider_secret_responds_without_leaking_reference(
    tmp_path, monkeypatch
):
    url, store, _ = migrated_db(tmp_path)
    store.register_provider(
        provider_id="openai", adapter="openai_compatible",
        base_url="https://provider.invalid/v1",
    )
    store.register_model(model_id="model-id", provider_id="openai", name="model-1")
    cap = CapabilityIA.ATENDIMENTO_INTERPRETACAO
    store.grant_capability(model_id="model-id", capability=cap)
    store.set_provider_health(provider_id="openai", status="healthy", circuit="closed")
    store.add_route(RouteDefinition(
        policy_id="route-1", scope="platform", tenant_id=None, unit_id=None,
        model_id="model-id", capability=cap, priority=100,
        price_snapshot_id="price-1", credential_source="fm_managed",
        secret_reference="env:FM_F3_MISSING_TEST_KEY",
    ))
    monkeypatch.delenv("FM_F3_MISSING_TEST_KEY", raising=False)
    cfg = CoreSettings(
        environment=CoreEnvironment.TEST, service_key="test-key", routes=(),
        control_plane_database_url=url,
    )
    with TestClient(create_app(cfg)) as client:
        response = client.post("/v1/ai/text",
            headers={"X-Core-Service-Key": "test-key"},
            json={
                "tenant_id": "tenant-a", "unit_id": "unit-1",
                "request_id": "req-1", "correlation_id": "corr-1",
                "system_prompt": "Atenda.",
                "messages": [{"role": "user", "content": "oi"}],
            },
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "core_control_plane_dependency_unavailable"
    assert "FM_F3_MISSING_TEST_KEY" not in response.text



def test_bootstrap_byok_is_disabled_unless_gateway_explicitly_injected(tmp_path):
    url, _, _ = migrated_db(tmp_path)
    runtime, engine = build_persistent_core(url)
    try:
        with pytest.raises(ControlPlaneError, match="byok_resolver_not_configured"):
            runtime._credentials.resolve(
                tenant_id="tenant-a",
                credential_source="tenant_managed",
                secret_reference="integration:tenant-a:credential-a",
            )
    finally:
        engine.dispose()


def test_bootstrap_explicit_gateway_maintains_tenant_boundary(tmp_path):
    url, _, _ = migrated_db(tmp_path)

    class ScopedGateway:
        def __init__(self):
            self.calls = []

        def resolve_active_secret(self, *, tenant_id, opaque_reference):
            self.calls.append((tenant_id, opaque_reference))
            if tenant_id != "tenant-a":
                raise PermissionError("unrecognized tenant")
            return SecretValue("isolated-test-byok-token")

    gateway = ScopedGateway()
    runtime, engine = build_persistent_core(url, tenant_gateway=gateway)
    try:
        result = runtime._credentials.resolve(
            tenant_id="tenant-a",
            credential_source="tenant_managed",
            secret_reference="integration:tenant-a:credential-a",
        )
        assert result.reveal() == "isolated-test-byok-token"
        assert gateway.calls == [("tenant-a", "credential-a")]

        with pytest.raises(ControlPlaneError):
            runtime._credentials.resolve(
                tenant_id="tenant-b",
                credential_source="tenant_managed",
                secret_reference="integration:tenant-a:credential-a",
            )
        assert gateway.calls == [("tenant-a", "credential-a")]
    finally:
        engine.dispose()


def test_bootstrap_rejects_ambiguous_credential_resolvers(tmp_path):
    url, _, _ = migrated_db(tmp_path)

    class Stub:
        def resolve(self, **kwargs):
            return SecretValue("test-token")

        def resolve_active_secret(self, **kwargs):
            return SecretValue("test-token")

    with pytest.raises(ValueError, match="credential_resolver_ambiguous"):
        build_persistent_core(
            url,
            credential_resolver=Stub(),
            tenant_gateway=Stub(),
        )


def test_bootstrap_can_wire_governed_plan_guard_without_real_provider(tmp_path):
    from datetime import timedelta

    from core.ai_plan_usage_guard import PlanQuotaPolicy

    url, _, _ = migrated_db(tmp_path)

    class SyntheticAuthority:
        def __init__(self):
            self.calls = 0

        def resolve(self, *, tenant_id, unit_id, capability, now):
            self.calls += 1
            return PlanQuotaPolicy(
                tenant_id=tenant_id, unit_id=unit_id,
                plan_code="ALL_FEATURES", revision=1,
                valid_until=now + timedelta(hours=1),
                input_bound=100, output_bound=100,
                scopes=(("ai.requests", "tenant"), ("ai.total_tokens", "tenant")),
            )

    authority = SyntheticAuthority()
    runtime, engine = build_persistent_core(url, plan_authority=authority)
    try:
        assert runtime._plan_usage is not None
        assert runtime._quota is None
        assert authority.calls == 0  # boot cannot silently spend or provision
    finally:
        engine.dispose()
