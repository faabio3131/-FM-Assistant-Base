"""Configuração explícita do runtime SaaS."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from dotenv import load_dotenv


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    environment: Environment
    database_url: str
    admin_key: str
    credential_pepper: str
    model_backend: str
    model_base_url: str | None
    model_api_key: str | None
    model_name: str | None
    auto_create_schema: bool

    @property
    def production_like(self) -> bool:
        return self.environment in {Environment.STAGING, Environment.PRODUCTION}

    def validate(self) -> "Settings":
        if not self.database_url.strip():
            raise RuntimeError("FM_ASSISTANT_DATABASE_URL obrigatório")
        if not self.admin_key.strip():
            raise RuntimeError("FM_ASSISTANT_ADMIN_KEY obrigatório")
        if not self.credential_pepper.strip():
            raise RuntimeError("FM_ASSISTANT_CREDENTIAL_PEPPER obrigatório")

        backend = self.model_backend.strip().casefold()
        if backend not in {"development", "openai_compatible"}:
            raise RuntimeError("FM_ASSISTANT_MODEL_BACKEND inválido")

        if self.production_like:
            if self.database_url.lower().startswith("sqlite"):
                raise RuntimeError("SQLite não é permitido em staging/production")
            if backend == "development":
                raise RuntimeError("Model gateway de desenvolvimento não é permitido em produção")
            if self.admin_key == "change-me-development":
                raise RuntimeError("FM_ASSISTANT_ADMIN_KEY padrão é proibida em produção")
            if self.credential_pepper == "change-me-development-pepper":
                raise RuntimeError("FM_ASSISTANT_CREDENTIAL_PEPPER padrão é proibido em produção")
            if len(self.admin_key) < 24:
                raise RuntimeError("FM_ASSISTANT_ADMIN_KEY deve ter ao menos 24 caracteres")
            if len(self.credential_pepper) < 32:
                raise RuntimeError("FM_ASSISTANT_CREDENTIAL_PEPPER deve ter ao menos 32 caracteres")

        if backend == "openai_compatible":
            if not all(
                value and value.strip()
                for value in (self.model_base_url, self.model_api_key, self.model_name)
            ):
                raise RuntimeError(
                    "MODEL_BASE_URL, MODEL_API_KEY e MODEL_NAME são obrigatórios "
                    "para openai_compatible"
                )
        return self


def load_settings() -> Settings:
    load_dotenv(override=False)
    raw_env = os.getenv("FM_ASSISTANT_ENV", "development").strip().casefold()
    try:
        environment = Environment(raw_env)
    except ValueError as exc:
        raise RuntimeError("FM_ASSISTANT_ENV inválido") from exc

    settings = Settings(
        environment=environment,
        database_url=os.getenv(
            "FM_ASSISTANT_DATABASE_URL",
            "sqlite:///./fm_assistant.db",
        ),
        admin_key=os.getenv("FM_ASSISTANT_ADMIN_KEY", "change-me-development"),
        credential_pepper=os.getenv(
            "FM_ASSISTANT_CREDENTIAL_PEPPER",
            "change-me-development-pepper",
        ),
        model_backend=os.getenv("FM_ASSISTANT_MODEL_BACKEND", "development"),
        model_base_url=os.getenv("FM_ASSISTANT_MODEL_BASE_URL"),
        model_api_key=os.getenv("FM_ASSISTANT_MODEL_API_KEY"),
        model_name=os.getenv("FM_ASSISTANT_MODEL_NAME"),
        auto_create_schema=_bool(
            "FM_ASSISTANT_AUTO_CREATE_SCHEMA",
            default=environment in {Environment.DEVELOPMENT, Environment.TEST},
        ),
    )
    return settings.validate()
