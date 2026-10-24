import pytest

from core.ai_router import CapabilityIA
from core.ai_service_settings import (
    CoreEnvironment,
    CoreSettings,
    ProviderRouteSettings,
)


def _route() -> ProviderRouteSettings:
    return ProviderRouteSettings(
        configuration_id="route-1",
        provider="gemini",
        model="model-1",
        capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
        priority=100,
        price_snapshot_id="price-1",
        adapter="gemini",
        base_url="https://example.invalid/v1",
        api_key="secret",
    )


def test_production_rejects_weak_service_key():
    with pytest.raises(RuntimeError):
        CoreSettings(
            environment=CoreEnvironment.PRODUCTION,
            service_key="short",
            routes=(_route(),),
        ).validate()


def test_production_requires_persisted_control_plane():
    with pytest.raises(RuntimeError, match="core_control_plane_required_in_commercial_env"):
        CoreSettings(
            environment=CoreEnvironment.PRODUCTION,
            service_key="x" * 48,
            routes=(_route(),),
        ).validate()


def test_production_accepts_distinct_keys_and_postgres():
    settings = CoreSettings(
        environment=CoreEnvironment.PRODUCTION,
        service_key="x" * 48,
        routes=(),
        control_plane_database_url="postgresql+psycopg://core:password@db.example/test",
        admin_key="y" * 48,
        assistant_plan_url="https://assistant.example.test",
        assistant_plan_signing_key="p" * 48,
    ).validate()
    assert settings.production_like is True
    assert settings.persistent_control_plane is True
    assert "password" not in repr(settings)


def test_production_rejects_sqlite_and_same_admin_key():
    with pytest.raises(RuntimeError, match="postgresql_required"):
        CoreSettings(
            environment=CoreEnvironment.PRODUCTION,
            service_key="x" * 48,
            routes=(),
            control_plane_database_url="sqlite:///test.db",
            admin_key="y" * 48,
        ).validate()

    with pytest.raises(RuntimeError, match="must_differ"):
        CoreSettings(
            environment=CoreEnvironment.PRODUCTION,
            service_key="x" * 48,
            routes=(),
            control_plane_database_url="postgresql://core:password@db.example/test",
            admin_key="x" * 48,
            assistant_plan_url="https://assistant.example.test",
            assistant_plan_signing_key="p" * 48,
        ).validate()
