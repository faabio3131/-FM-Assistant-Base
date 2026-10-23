from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import (
    AIControlPlaneStore,
    ControlPlaneBase,
    ControlPlaneError,
    RouteDefinition,
)
from core.ai_router import CapabilityIA

CAP = CapabilityIA.ATENDIMENTO_INTERPRETACAO


@pytest.fixture
def plane(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control-plane.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    store = AIControlPlaneStore(sessionmaker(engine, expire_on_commit=False))
    store.register_provider(
        provider_id="gemini", adapter="gemini", base_url="https://gemini.invalid/v1beta"
    )
    store.register_model(model_id="model-1", provider_id="gemini", name="text-1")
    store.grant_capability(model_id="model-1", capability=CAP)
    store.set_provider_health(provider_id="gemini", status="healthy", circuit="closed")
    yield store, engine
    engine.dispose()


def definition(policy_id, *, scope="platform", tenant=None, unit=None, priority=100):
    return RouteDefinition(
        policy_id=policy_id,
        scope=scope,
        tenant_id=tenant,
        unit_id=unit,
        model_id="model-1",
        capability=CAP,
        priority=priority,
        price_snapshot_id="price-1",
        credential_source="fm_managed",
        secret_reference="env:FM_TEST_PROVIDER",
    )


def test_scope_precedence_isolation_and_persistence(plane):
    store, engine = plane
    store.add_route(definition("platform"))
    store.add_route(definition("tenant", scope="tenant", tenant="a"))
    store.add_route(definition("unit", scope="unit", tenant="a", unit="one"))
    assert store.resolve(tenant_id="a", unit_id="one", capability=CAP)[0].route.configuracao_id == "unit"
    assert store.resolve(tenant_id="a", unit_id="two", capability=CAP)[0].route.configuracao_id == "tenant"
    assert store.resolve(tenant_id="b", unit_id="one", capability=CAP)[0].route.configuracao_id == "platform"
    other_session = AIControlPlaneStore(sessionmaker(engine, expire_on_commit=False))
    assert other_session.resolve(tenant_id="a", unit_id="one", capability=CAP)[0].scope == "unit"


def test_ambiguous_priority_fails_closed(plane):
    store, _ = plane
    store.add_route(definition("one", priority=100))
    store.add_route(definition("two", priority=100))
    with pytest.raises(ControlPlaneError, match="ambiguous_priority"):
        store.resolve(tenant_id="a", unit_id="one", capability=CAP)


def test_unhealthy_scoped_routes_do_not_silently_fall_back_to_platform(plane):
    store, _ = plane
    store.add_route(definition("global"))
    store.add_route(definition("specific", scope="unit", tenant="a", unit="one"))
    store.set_provider_health(provider_id="gemini", status="unavailable", circuit="open")
    with pytest.raises(ControlPlaneError, match="no_healthy_route"):
        store.resolve(tenant_id="a", unit_id="one", capability=CAP)


def test_no_route_when_health_unknown(plane):
    store, _ = plane
    store.add_route(definition("global"))
    store.set_provider_health(provider_id="gemini", status="unknown", circuit="closed")
    with pytest.raises(ControlPlaneError, match="no_healthy_route"):
        store.resolve(tenant_id="a", unit_id="one", capability=CAP)


def test_secret_reference_and_byok_tenant_boundaries(plane):
    store, engine = plane
    bad = replace(definition("raw-key"), secret_reference="sk-secret-value")
    with pytest.raises(ControlPlaneError, match="fm_secret_reference_invalid"):
        store.add_route(bad)
    byok = replace(
        definition("byok", scope="tenant", tenant="a"),
        credential_source="tenant_managed",
        secret_reference="integration:b:credential-1",
    )
    with pytest.raises(ControlPlaneError, match="byok_tenant_mismatch"):
        store.add_route(byok)
    good = replace(byok, secret_reference="integration:a:credential-1")
    store.add_route(good)
    result = store.resolve(tenant_id="a", unit_id="one", capability=CAP)[0]
    assert result.secret_reference == "integration:a:credential-1"
    assert not hasattr(result, "api_key")
    assert "core_ai_route_policies" in inspect(engine).get_table_names()


def test_invalid_scope_rejected_before_persistence(plane):
    store, _ = plane
    invalid = definition("bad", scope="platform", tenant="a")
    with pytest.raises(ControlPlaneError, match="platform_scope_invalid"):
        store.add_route(invalid)


def test_schema_downgrade_on_disposable_database(plane):
    _, engine = plane
    assert "core_ai_providers" in inspect(engine).get_table_names()
    ControlPlaneBase.metadata.drop_all(engine)
    assert "core_ai_providers" not in inspect(engine).get_table_names()
