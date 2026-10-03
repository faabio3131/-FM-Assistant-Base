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


def test_production_accepts_strong_service_key():
    settings = CoreSettings(
        environment=CoreEnvironment.PRODUCTION,
        service_key="x" * 48,
        routes=(_route(),),
    ).validate()
    assert settings.production_like is True
