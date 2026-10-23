"""Single-product bootstrap: isolated Core process, one public Assistant entry."""
from __future__ import annotations

import pytest

from scripts.vendeatendeia_dev import configure_product


def local_config(**overrides):
    env = {
        "FM_VENDEATENDEIA_INTERNAL_KEY": "valid-internal-only-credential-0ffline-2026",
        "FM_CORE_AI_ROUTES_JSON": "[]",
    }
    env.update(overrides)
    return configure_product(env)


def test_vendeatendeia_runs_one_product_with_private_core():
    runtime = local_config()
    assert runtime.core_port == 8765
    assert runtime.app_port == 8000
    assert runtime.core_environment["FM_CORE_SERVICE_KEY"] == (
        runtime.assistant_environment["FM_ASSISTANT_CORE_SERVICE_KEY"]
    )
    assert runtime.assistant_environment["FM_ASSISTANT_CORE_BASE_URL"] == (
        "http://127.0.0.1:8765"
    )
    assert runtime.assistant_environment["FM_ASSISTANT_MODEL_BACKEND"] == "core"
    assert runtime.core_environment["PYTHONPATH"].endswith("services\\fm-core") or (
        runtime.core_environment["PYTHONPATH"].endswith("services/fm-core")
    )


@pytest.mark.parametrize("overrides", [
    {"FM_VENDEATENDEIA_INTERNAL_KEY": ""},
    {"FM_VENDEATENDEIA_INTERNAL_KEY": "replace-with-a-secret"},
    {"FM_ASSISTANT_MODEL_BACKEND": "development"},
    {"FM_ASSISTANT_CORE_BASE_URL": "https://untrusted.example"},
    {"FM_CORE_SERVICE_KEY": "other-secret"},
    {"FM_ASSISTANT_CORE_SERVICE_KEY": "other-secret"},
    {"FM_ASSISTANT_ENV": "production"},
    {"FM_CORE_ENV": "staging"},
    {"FM_VENDEATENDEIA_CORE_PORT": "8000"},
    {"FM_VENDEATENDEIA_CORE_PORT": "0"},
    {"FM_VENDEATENDEIA_APP_PORT": "8765"},
])
def test_single_product_rejects_divergent_configuration(overrides):
    with pytest.raises(ValueError):
        local_config(**overrides)


def test_no_core_configuration_starts_no_runtime():
    with pytest.raises(ValueError, match="core_routes_or_database_required"):
        configure_product({
            "FM_VENDEATENDEIA_INTERNAL_KEY": "valid-internal-only-credential-0ffline-2026",
        })


def test_config_can_use_shared_persistent_core_database():
    configured = configure_product({
        "FM_VENDEATENDEIA_INTERNAL_KEY": "valid-internal-only-credential-0ffline-2026",
        "FM_CORE_CONTROL_PLANE_DATABASE_URL": "sqlite:///./core.db",
        "FM_VENDEATENDEIA_CORE_PORT": "8766",
        "FM_VENDEATENDEIA_APP_PORT": "8010",
    })
    assert configured.core_port == 8766
    assert configured.app_port == 8010
    assert configured.assistant_environment["FM_ASSISTANT_CORE_BASE_URL"].endswith(":8766")
