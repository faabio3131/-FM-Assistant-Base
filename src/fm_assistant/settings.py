"""Configuração explícita do runtime SaaS."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
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
    channel_encryption_key: str
    session_pepper: str
    session_ttl_minutes: int
    model_backend: str
    model_base_url: str | None
    model_api_key: str | None
    model_name: str | None
    core_base_url: str | None
    core_service_key: str | None
    auto_create_schema: bool
    core_bridge_key_id: str | None = None
    core_bridge_signing_key: str | None = field(default=None, repr=False)
    command_control_key_id: str | None = None
    command_control_signing_key: str | None = field(default=None, repr=False)
    trusted_command_organization_id: str | None = None
    core_plan_signing_key: str | None = field(default=None, repr=False)
    evolution_origin: str | None = None
    evolution_global_key: str | None = field(default=None, repr=False)
    evolution_webhook_signing_key: str | None = field(default=None, repr=False)

    @property
    def production_like(self) -> bool:
        return self.environment in {Environment.STAGING, Environment.PRODUCTION}

    def validate(self) -> Settings:
        if not self.database_url.strip():
            raise RuntimeError("FM_ASSISTANT_DATABASE_URL obrigatório")
        if not self.admin_key.strip():
            raise RuntimeError("FM_ASSISTANT_ADMIN_KEY obrigatório")
        if not self.credential_pepper.strip():
            raise RuntimeError("FM_ASSISTANT_CREDENTIAL_PEPPER obrigatório")
        if not self.channel_encryption_key.strip():
            raise RuntimeError("FM_ASSISTANT_CHANNEL_ENCRYPTION_KEY obrigatório")
        if not self.session_pepper.strip():
            raise RuntimeError("FM_ASSISTANT_SESSION_PEPPER obrigatório")
        if not 15 <= self.session_ttl_minutes <= 10080:
            raise RuntimeError("FM_ASSISTANT_SESSION_TTL_MINUTES inválido")

        if bool(self.core_bridge_key_id) != bool(self.core_bridge_signing_key):
            raise RuntimeError("FM_ASSISTANT_CORE_BRIDGE_CONFIG_INCOMPLETE")
        if self.core_bridge_signing_key:
            if (
                len(self.core_bridge_signing_key) < 32
                or not self.core_bridge_key_id
                or len(self.core_bridge_key_id) > 64
            ):
                raise RuntimeError("FM_ASSISTANT_CORE_BRIDGE_CONFIG_INVALID")
            if self.core_bridge_signing_key in {
                self.admin_key, self.credential_pepper, self.session_pepper,
                self.core_service_key, self.channel_encryption_key,
            }:
                raise RuntimeError("FM_ASSISTANT_CORE_BRIDGE_KEY_REUSED")
        command_fields = (
            self.command_control_key_id,
            self.command_control_signing_key,
            self.trusted_command_organization_id,
        )
        if any(command_fields) and not all(command_fields):
            raise RuntimeError("FM_ASSISTANT_COMMAND_CONTROL_CONFIG_INCOMPLETE")
        if all(command_fields):
            if not self.core_bridge_key_id or not self.core_bridge_signing_key:
                raise RuntimeError("FM_ASSISTANT_COMMAND_CONTROL_REQUIRES_CORE_IDENTITY")
            if len(self.command_control_signing_key or "") < 32:
                raise RuntimeError("FM_ASSISTANT_COMMAND_CONTROL_KEY_INVALID")
            if len(self.command_control_key_id or "") > 64:
                raise RuntimeError("FM_ASSISTANT_COMMAND_CONTROL_KEY_ID_INVALID")
            if len(self.trusted_command_organization_id or "") > 128:
                raise RuntimeError("FM_ASSISTANT_COMMAND_CONTROL_ORGANIZATION_INVALID")
            if self.command_control_signing_key in {
                self.core_bridge_signing_key, self.admin_key,
                self.credential_pepper, self.session_pepper,
                self.core_service_key, self.channel_encryption_key,
            }:
                raise RuntimeError("FM_ASSISTANT_COMMAND_CONTROL_KEY_REUSED")
        if self.core_plan_signing_key is not None:
            if len(self.core_plan_signing_key) < 32 or self.core_plan_signing_key in {
                self.admin_key, self.credential_pepper, self.session_pepper,
                self.channel_encryption_key, self.core_service_key,
                self.core_bridge_signing_key, self.command_control_signing_key,
            }:
                raise RuntimeError("FM_ASSISTANT_CORE_PLAN_SIGNING_KEY_INVALID")
        if bool(self.evolution_origin) != bool(self.evolution_global_key):
            raise RuntimeError("FM_ASSISTANT_EVOLUTION_CONFIG_INCOMPLETE")
        if self.evolution_origin and self.evolution_global_key:
            from .channels.whatsapp_evolution import EvolutionSettings
            try:
                EvolutionSettings(
                    origin=self.evolution_origin,
                    global_key=self.evolution_global_key,
                )
            except ValueError as exc:
                raise RuntimeError("FM_ASSISTANT_EVOLUTION_CONFIG_INVALID") from exc
            if self.evolution_global_key in {
                self.admin_key, self.credential_pepper, self.session_pepper,
                self.channel_encryption_key, self.core_service_key,
                self.command_control_signing_key, self.core_bridge_signing_key,
                self.core_plan_signing_key, self.model_api_key,
            }:
                raise RuntimeError("FM_ASSISTANT_EVOLUTION_KEY_REUSED")
        if self.evolution_webhook_signing_key:
            if not self.evolution_origin or not self.evolution_global_key:
                raise RuntimeError("FM_ASSISTANT_EVOLUTION_WEBHOOK_REQUIRES_GATEWAY")
            if len(self.evolution_webhook_signing_key) < 32:
                raise RuntimeError("FM_ASSISTANT_EVOLUTION_WEBHOOK_SIGNER_INVALID")
            if self.evolution_webhook_signing_key in {
                self.evolution_global_key, self.admin_key,
                self.credential_pepper, self.channel_encryption_key,
                self.session_pepper, self.core_service_key,
                self.core_bridge_signing_key, self.command_control_signing_key,
                self.core_plan_signing_key,
            }:
                raise RuntimeError("FM_ASSISTANT_EVOLUTION_WEBHOOK_SIGNER_REUSED")
        backend = self.model_backend.strip().casefold()
        if backend not in {"development", "openai_compatible", "core"}:
            raise RuntimeError("FM_ASSISTANT_MODEL_BACKEND inválido")

        if self.production_like:
            if self.database_url.lower().startswith("sqlite"):
                raise RuntimeError("SQLite não é permitido em staging/production")
            if backend != "core":
                raise RuntimeError("FM Core Base é obrigatório em staging/production")
            if self.admin_key == "change-me-development":
                raise RuntimeError("FM_ASSISTANT_ADMIN_KEY padrão é proibida em produção")
            if self.credential_pepper == "change-me-development-pepper":
                raise RuntimeError("FM_ASSISTANT_CREDENTIAL_PEPPER padrão é proibido em produção")
            if self.channel_encryption_key == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=":
                raise RuntimeError("FM_ASSISTANT_CHANNEL_ENCRYPTION_KEY padrão é proibida em produção")
            if len(self.admin_key) < 24:
                raise RuntimeError("FM_ASSISTANT_ADMIN_KEY deve ter ao menos 24 caracteres")
            if len(self.credential_pepper) < 32:
                raise RuntimeError("FM_ASSISTANT_CREDENTIAL_PEPPER deve ter ao menos 32 caracteres")
            if len(self.session_pepper) < 32:
                raise RuntimeError("FM_ASSISTANT_SESSION_PEPPER deve ter ao menos 32 caracteres")

        if backend == "openai_compatible":
            if not all(
                value and value.strip()
                for value in (self.model_base_url, self.model_api_key, self.model_name)
            ):
                raise RuntimeError(
                    "MODEL_BASE_URL, MODEL_API_KEY e MODEL_NAME são obrigatórios "
                    "para openai_compatible"
                )

        if backend == "core":
            if not all(
                value and value.strip()
                for value in (self.core_base_url, self.core_service_key)
            ):
                raise RuntimeError(
                    "FM_ASSISTANT_CORE_BASE_URL e FM_ASSISTANT_CORE_SERVICE_KEY "
                    "são obrigatórios para backend core"
                )
            if self.production_like and len(self.core_service_key or "") < 32:
                raise RuntimeError(
                    "FM_ASSISTANT_CORE_SERVICE_KEY deve ter ao menos 32 caracteres"
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
        channel_encryption_key=os.getenv(
            "FM_ASSISTANT_CHANNEL_ENCRYPTION_KEY",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        ),
        session_pepper=os.getenv(
            "FM_ASSISTANT_SESSION_PEPPER",
            "change-me-development-session-pepper",
        ),
        session_ttl_minutes=int(os.getenv("FM_ASSISTANT_SESSION_TTL_MINUTES", "480")),
        model_backend=os.getenv("FM_ASSISTANT_MODEL_BACKEND", "development"),
        model_base_url=os.getenv("FM_ASSISTANT_MODEL_BASE_URL"),
        model_api_key=os.getenv("FM_ASSISTANT_MODEL_API_KEY"),
        model_name=os.getenv("FM_ASSISTANT_MODEL_NAME"),
        core_base_url=os.getenv("FM_ASSISTANT_CORE_BASE_URL"),
        core_service_key=os.getenv("FM_ASSISTANT_CORE_SERVICE_KEY"),
        core_plan_signing_key=os.getenv("FM_ASSISTANT_CORE_PLAN_SIGNING_KEY") or None,
        evolution_origin=os.getenv("FM_ASSISTANT_EVOLUTION_ORIGIN") or None,
        evolution_global_key=os.getenv("FM_ASSISTANT_EVOLUTION_GLOBAL_KEY") or None,
        evolution_webhook_signing_key=(
            os.getenv("FM_ASSISTANT_EVOLUTION_WEBHOOK_SIGNING_KEY") or None
        ),
        core_bridge_key_id=os.getenv("FM_ASSISTANT_CORE_BRIDGE_KEY_ID") or None,
        core_bridge_signing_key=os.getenv("FM_ASSISTANT_CORE_BRIDGE_SIGNING_KEY") or None,
        command_control_key_id=os.getenv("FM_ASSISTANT_COMMAND_CONTROL_KEY_ID") or None,
        command_control_signing_key=os.getenv("FM_ASSISTANT_COMMAND_CONTROL_SIGNING_KEY") or None,
        trusted_command_organization_id=os.getenv(
            "FM_ASSISTANT_TRUSTED_COMMAND_ORGANIZATION_ID"
        ) or None,
        auto_create_schema=_bool(
            "FM_ASSISTANT_AUTO_CREATE_SCHEMA",
            default=environment in {Environment.DEVELOPMENT, Environment.TEST},
        ),
    )
    return settings.validate()
