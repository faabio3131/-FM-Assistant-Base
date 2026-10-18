"""ConfiguraÃ§Ã£o explÃ­cita das rotas multimodelo do Core."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from dotenv import load_dotenv

from core.ai_router import CapabilityIA


class CoreEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True, kw_only=True)
class ProviderRouteSettings:
    configuration_id: str
    provider: str
    model: str
    capability: CapabilityIA
    priority: int
    price_snapshot_id: str
    adapter: str
    base_url: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        required = (
            self.configuration_id,
            self.provider,
            self.model,
            self.price_snapshot_id,
            self.adapter,
            self.base_url,
            self.api_key,
        )
        if not all(value.strip() for value in required):
            raise ValueError("core_ai_route_incomplete")
        if self.adapter not in {"openai_compatible", "gemini"}:
            raise ValueError("core_ai_adapter_invalid")
        if not self.base_url.startswith("https://"):
            raise ValueError("core_ai_base_url_requires_https")
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError("core_ai_timeout_invalid")


@dataclass(frozen=True, kw_only=True)
class CoreSettings:
    environment: CoreEnvironment
    service_key: str
    routes: tuple[ProviderRouteSettings, ...]

    @property
    def production_like(self) -> bool:
        return self.environment in {CoreEnvironment.STAGING, CoreEnvironment.PRODUCTION}

    def validate(self) -> CoreSettings:
        if not self.service_key.strip():
            raise RuntimeError("FM_CORE_SERVICE_KEY obrigatÃ³rio")
        if not self.routes:
            raise RuntimeError("FM_CORE_AI_ROUTES_JSON deve conter ao menos uma rota")
        if self.production_like:
            if self.service_key == "change-me-development-core-key":
                raise RuntimeError("FM_CORE_SERVICE_KEY padrÃ£o Ã© proibida em produÃ§Ã£o")
            if len(self.service_key) < 32:
                raise RuntimeError("FM_CORE_SERVICE_KEY deve ter ao menos 32 caracteres")
        return self


def _route_from_payload(payload: Any) -> ProviderRouteSettings:
    if not isinstance(payload, dict):
        raise TypeError("rota de IA deve ser objeto JSON")
    api_key_env = str(payload.get("api_key_env", "")).strip()
    if not api_key_env:
        raise RuntimeError("api_key_env obrigatÃ³rio em cada rota")
    api_key = os.getenv(api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"segredo de provider ausente: {api_key_env}")
    try:
        capability = CapabilityIA(str(payload["capability"]))
    except (KeyError, ValueError) as exc:
        raise RuntimeError("capability de rota invÃ¡lida") from exc
    try:
        return ProviderRouteSettings(
            configuration_id=str(payload["configuration_id"]),
            provider=str(payload["provider"]).strip().casefold(),
            model=str(payload["model"]),
            capability=capability,
            priority=int(payload["priority"]),
            price_snapshot_id=str(payload["price_snapshot_id"]),
            adapter=str(payload["adapter"]).strip().casefold(),
            base_url=str(payload["base_url"]).rstrip("/"),
            api_key=api_key,
            timeout_seconds=float(payload.get("timeout_seconds", 30.0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("configuraÃ§Ã£o de rota de IA invÃ¡lida") from exc


def load_settings() -> CoreSettings:
    load_dotenv(override=False)
    raw_env = os.getenv("FM_CORE_ENV", "development").strip().casefold()
    try:
        environment = CoreEnvironment(raw_env)
    except ValueError as exc:
        raise RuntimeError("FM_CORE_ENV invÃ¡lido") from exc

    raw_routes = os.getenv("FM_CORE_AI_ROUTES_JSON", "")
    try:
        payload = json.loads(raw_routes)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FM_CORE_AI_ROUTES_JSON invÃ¡lido") from exc
    if not isinstance(payload, list):
        raise TypeError("FM_CORE_AI_ROUTES_JSON deve ser uma lista")

    return CoreSettings(
        environment=environment,
        service_key=os.getenv("FM_CORE_SERVICE_KEY", "change-me-development-core-key"),
        routes=tuple(_route_from_payload(item) for item in payload),
    ).validate()

