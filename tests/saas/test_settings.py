import pytest

from fm_assistant.settings import Environment, Settings


def test_production_rejects_development_secrets_and_backend():
    with pytest.raises(RuntimeError):
        Settings(
            environment=Environment.PRODUCTION,
            database_url="postgresql://user:pass@db/app",
            admin_key="change-me-development",
            credential_pepper="change-me-development-pepper",
            channel_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            model_backend="development",
            model_base_url=None,
            model_api_key=None,
            model_name=None,
            core_base_url=None,
            core_service_key=None,
            auto_create_schema=False,
        ).validate()


def test_production_accepts_strong_openai_compatible_configuration():
    settings = Settings(
        environment=Environment.PRODUCTION,
        database_url="postgresql://user:pass@db/app",
        admin_key="a" * 32,
        credential_pepper="b" * 48,
        channel_encryption_key="YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI=",
        model_backend="openai_compatible",
        model_base_url="https://example.invalid/v1",
        model_api_key="secret-key",
        model_name="model-x",
        core_base_url=None,
        core_service_key=None,
        auto_create_schema=False,
    ).validate()

    assert settings.production_like is True


def test_production_accepts_core_backend_configuration():
    settings = Settings(
        environment=Environment.PRODUCTION,
        database_url="postgresql://user:pass@db/app",
        admin_key="a" * 32,
        credential_pepper="b" * 48,
        channel_encryption_key="YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI=",
        model_backend="core",
        model_base_url=None,
        model_api_key=None,
        model_name=None,
        core_base_url="https://core.internal",
        core_service_key="c" * 48,
        auto_create_schema=False,
    ).validate()

    assert settings.model_backend == "core"
