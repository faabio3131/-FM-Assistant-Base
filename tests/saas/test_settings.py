import pytest

from fm_assistant.settings import Environment, Settings


def _settings(**overrides):
    values = {
        "environment": Environment.PRODUCTION,
        "database_url": "postgresql://user:pass@db/app",
        "admin_key": "a" * 32,
        "credential_pepper": "b" * 48,
        "channel_encryption_key": "YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI=",
        "session_pepper": "s" * 48,
        "session_ttl_minutes": 480,
        "model_backend": "core",
        "model_base_url": None,
        "model_api_key": None,
        "model_name": None,
        "core_base_url": "https://core.internal",
        "core_service_key": "c" * 48,
        "auto_create_schema": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_development_secrets_and_backend():
    with pytest.raises(RuntimeError):
        _settings(
            admin_key="change-me-development",
            credential_pepper="change-me-development-pepper",
            session_pepper="change-me-development-session-pepper",
            model_backend="development",
            core_base_url=None,
            core_service_key=None,
        ).validate()


def test_production_rejects_direct_openai_compatible_backend():
    with pytest.raises(RuntimeError, match="FM Core Base"):
        _settings(
            model_backend="openai_compatible",
            model_base_url="https://example.invalid/v1",
            model_api_key="secret-key",
            model_name="model-x",
            core_base_url=None,
            core_service_key=None,
        ).validate()


def test_development_allows_direct_openai_compatible_configuration():
    settings = _settings(
        environment=Environment.DEVELOPMENT,
        database_url="sqlite:///./dev.db",
        model_backend="openai_compatible",
        model_base_url="https://example.invalid/v1",
        model_api_key="secret-key",
        model_name="model-x",
        core_base_url=None,
        core_service_key=None,
        auto_create_schema=True,
    ).validate()

    assert settings.model_backend == "openai_compatible"


def test_production_accepts_core_backend_configuration():
    settings = _settings().validate()

    assert settings.production_like is True
    assert settings.model_backend == "core"


@pytest.mark.parametrize("unsafe", [
    "http://core.internal", "https://user:secret@core.internal",
    "https://core.internal/proxy", "https://core.internal?key=a",
    "https://core.internal/#fragment",
])
def test_production_rejects_untrusted_core_origin(unsafe):
    with pytest.raises(RuntimeError, match="FM_ASSISTANT_CORE_TLS_REQUIRED"):
        _settings(core_base_url=unsafe).validate()
