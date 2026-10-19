"""ConfiguraÃ§Ã£o explÃ­cita das rotas multimodelo do Core."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

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
    max_output_tokens: int | None = None

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
        if self.max_output_tokens is not None and (
            type(self.max_output_tokens) is not int
            or not 1 <= self.max_output_tokens <= 1_000_000
        ):
            raise ValueError("core_ai_output_ceiling_invalid")


@dataclass(frozen=True, kw_only=True)
class CoreSettings:
    environment: CoreEnvironment
    service_key: str = field(repr=False)
    routes: tuple[ProviderRouteSettings, ...]
    control_plane_database_url: str | None = field(default=None, repr=False)
    admin_key: str | None = field(default=None, repr=False)
    assistant_bridge_url: str | None = None
    assistant_bridge_key_id: str | None = None
    assistant_bridge_signing_key: str | None = field(default=None, repr=False)
    assistant_plan_url: str | None = None
    assistant_plan_signing_key: str | None = field(default=None, repr=False)
    
    @property
    def persistent_control_plane(self) -> bool:
        return self.control_plane_database_url is not None

    @property
    def production_like(self) -> bool:
        return self.environment in {CoreEnvironment.STAGING, CoreEnvironment.PRODUCTION}

    def validate(self) -> CoreSettings:
        enabled = (
            self.assistant_bridge_url,
            self.assistant_bridge_key_id,
            self.assistant_bridge_signing_key,
        )
        if any(enabled) and not all(enabled):
            raise RuntimeError("core_assistant_bridge_config_incomplete")
        if all(enabled):
            if not self.persistent_control_plane:
                raise RuntimeError("core_assistant_bridge_requires_control_plane")
            from core.ai_assistant_credential_gateway import (
                AssistantSignedCredentialGateway,
            )
            try:
                AssistantSignedCredentialGateway(
                    base_url=self.assistant_bridge_url or "",
                    key_id=self.assistant_bridge_key_id or "",
                    signing_key=self.assistant_bridge_signing_key or "",
                )
            except ValueError as exc:
                raise RuntimeError("core_assistant_bridge_config_invalid") from exc
            if self.assistant_bridge_signing_key in (self.service_key, self.admin_key):
                raise RuntimeError("core_assistant_bridge_key_reused")
        plan_fields = (self.assistant_plan_url, self.assistant_plan_signing_key)
        if any(plan_fields) and not all(plan_fields):
            raise RuntimeError("core_plan_authority_config_incomplete")
        if all(plan_fields):
            if not self.persistent_control_plane:
                raise RuntimeError("core_plan_authority_requires_control_plane")
            if len(self.assistant_plan_signing_key or "") < 32:
                raise RuntimeError("core_plan_authority_key_invalid")
            if self.assistant_plan_signing_key in (
                self.service_key, self.admin_key, self.assistant_bridge_signing_key,
            ):
                raise RuntimeError("core_plan_authority_key_reused")
            from core.ai_signed_plan_authority import AssistantPlanHTTPSFetch
            import httpx

            with httpx.Client() as verify_client:
                try:
                    AssistantPlanHTTPSFetch(
                        origin=self.assistant_plan_url or "",
                        secret=(self.assistant_plan_signing_key or "").encode(),
                        bounds=lambda capability: (4096, 2048),
                        client=verify_client,
                    )
                except ValueError as exc:
                    raise RuntimeError("core_plan_authority_url_invalid") from exc
        if not self.service_key.strip():
            raise RuntimeError("FM_CORE_SERVICE_KEY obrigatorio")
        if self.persistent_control_plane:
            url = (self.control_plane_database_url or "").strip()
            if not url:
                raise RuntimeError("core_control_plane_database_url_required")
            try:
                parsed = make_url(url)
            except ArgumentError as exc:
                raise RuntimeError("core_control_plane_database_url_invalid") from exc
            if parsed.get_backend_name() not in {"sqlite", "postgresql"}:
                raise RuntimeError("core_control_plane_database_backend_invalid")
            if self.routes:
                raise RuntimeError("core_control_plane_static_routes_forbidden")
            if self.production_like and parsed.get_backend_name() != "postgresql":
                raise RuntimeError("core_control_plane_postgresql_required")
        elif not self.routes:
            raise RuntimeError("FM_CORE_AI_ROUTES_JSON deve conter ao menos uma rota")
        if self.production_like:
            if self.service_key == "change-me-development-core-key":
                raise RuntimeError("FM_CORE_SERVICE_KEY default proibida")
            if len(self.service_key) < 32:
                raise RuntimeError("FM_CORE_SERVICE_KEY deve ter 32+ caracteres")
            if not self.persistent_control_plane:
                raise RuntimeError("core_control_plane_required_in_commercial_env")
            if not all(plan_fields):
                raise RuntimeError("core_plan_authority_required_in_commercial_env")
            if not self.admin_key or len(self.admin_key) < 32:
                raise RuntimeError("FM_CORE_ADMIN_KEY must have 32+ characters")
            if self.admin_key == self.service_key:
                raise RuntimeError("core_admin_service_key_must_differ")
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
            max_output_tokens=payload.get("max_output_tokens"),
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

    db_url = os.getenv("FM_CORE_CONTROL_PLANE_DATABASE_URL", "").strip() or None
    raw_routes = os.getenv("FM_CORE_AI_ROUTES_JSON", "")
    if db_url:
        if raw_routes.strip():
            raise RuntimeError("core_control_plane_static_routes_forbidden")
        payload: list[Any] = []
    else:
        try:
            payload = json.loads(raw_routes)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FM_CORE_AI_ROUTES_JSON invalido") from exc
        if not isinstance(payload, list):
            raise TypeError("FM_CORE_AI_ROUTES_JSON deve ser uma lista")

    return CoreSettings(
        environment=environment,
        service_key=os.getenv("FM_CORE_SERVICE_KEY", "change-me-development-core-key"),
        routes=tuple(_route_from_payload(item) for item in payload),
        control_plane_database_url=db_url,
        admin_key=os.getenv("FM_CORE_ADMIN_KEY") or None,
        assistant_bridge_url=os.getenv("FM_CORE_ASSISTANT_BRIDGE_URL") or None,
        assistant_bridge_key_id=os.getenv("FM_CORE_ASSISTANT_BRIDGE_KEY_ID") or None,
        assistant_bridge_signing_key=os.getenv("FM_CORE_ASSISTANT_BRIDGE_SIGNING_KEY") or None,
        assistant_plan_url=os.getenv("FM_CORE_ASSISTANT_PLAN_URL") or None,
        assistant_plan_signing_key=os.getenv("FM_CORE_ASSISTANT_PLAN_SIGNING_KEY") or None,
    ).validate()
