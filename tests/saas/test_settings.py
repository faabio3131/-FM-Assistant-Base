import pytest

from fm_assistant.settings import Environment, Settings


def test_production_rejects_development_secrets_and_backend():
    with pytest.raises(RuntimeError):
        Settings(
            environment=Environment.PRODUCTION,
            database_url="postgresql://user:pass@db/app",
            admin_key="change-me-development",
            credential_pepper="change-me-development-pepper",
            model_backend="development",
            model_base_url=None,
            model_api_key=None,
            model_name=None,
            auto_create_schema=False,
        ).validate()


def test_production_accepts_strong_openai_compatible_configuration():
    settings = Settings(
        environment=Environment.PRODUCTION,
        database_url="postgresql://user:pass@db/app",
        admin_key="a" * 32,
        credential_pepper="b" * 48,
        model_backend="openai_compatible",
        model_base_url="https://example.invalid/v1",
        model_api_key="secret-key",
        model_name="model-x",
        auto_create_schema=False,
    ).validate()

    assert settings.production_like is True
