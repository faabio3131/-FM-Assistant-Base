"""Primeira fatia persistente do FM Core AI Control Plane (F3).

Somente identificadores e referencias de segredos sao persistidos.
Esta camada nao autentica administradores: a futura API administrativa devera
validar autoridade separada antes de chamar qualquer mutacao.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from core.ai_router import CapabilityIA, RotaIA


class ControlPlaneError(ValueError):
    """Falha fechada para configuracao ou politica inconsistente."""


class ControlPlaneBase(DeclarativeBase):
    pass


class AIProvider(ControlPlaneBase):
    __tablename__ = "core_ai_providers"

    provider_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    adapter: Mapped[str] = mapped_column(String(40), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AIModel(ControlPlaneBase):
    __tablename__ = "core_ai_models"

    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("core_ai_providers.provider_id"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AIModelCapability(ControlPlaneBase):
    __tablename__ = "core_ai_model_capabilities"
    __table_args__ = (UniqueConstraint("model_id", "capability"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("core_ai_models.model_id"))
    capability: Mapped[str] = mapped_column(String(80), nullable=False)


class AIRoutePolicy(ControlPlaneBase):
    __tablename__ = "core_ai_route_policies"

    policy_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope: Mapped[str] = mapped_column(String(12), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(128))
    unit_id: Mapped[str | None] = mapped_column(String(128))
    model_id: Mapped[str] = mapped_column(ForeignKey("core_ai_models.model_id"))
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    price_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_source: Mapped[str] = mapped_column(String(20), nullable=False)
    secret_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AIProviderHealth(ControlPlaneBase):
    __tablename__ = "core_ai_provider_health"

    provider_id: Mapped[str] = mapped_column(
        ForeignKey("core_ai_providers.provider_id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    circuit: Mapped[str] = mapped_column(String(12), nullable=False)


@dataclass(frozen=True, kw_only=True)
class RouteDefinition:
    policy_id: str
    scope: str
    tenant_id: str | None
    unit_id: str | None
    model_id: str
    capability: CapabilityIA
    priority: int
    price_snapshot_id: str
    credential_source: str
    secret_reference: str
    timeout_seconds: int = 30


@dataclass(frozen=True, kw_only=True)
class ResolvedCoreRoute:
    route: RotaIA
    scope: str
    adapter: str
    base_url: str
    credential_source: str
    secret_reference: str
    timeout_seconds: int


def _require_id(value: str | None, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError(f"core_control_plane.{field}_required")
    return value.strip()


def _check_reference(definition: RouteDefinition) -> None:
    source = definition.credential_source
    ref = definition.secret_reference
    if not ref or len(ref) > 512 or any(char.isspace() for char in ref):
        raise ControlPlaneError("core_control_plane.secret_reference_invalid")
    if any(char in ref for char in ("?", "#", "@", "/", "\\")):
        raise ControlPlaneError("core_control_plane.secret_reference_invalid")
    if source == "fm_managed":
        if not ref.startswith(("env:", "vault:")) or not ref.split(":", 1)[1]:
            raise ControlPlaneError("core_control_plane.fm_secret_reference_invalid")
    elif source == "tenant_managed":
        tenant = _require_id(definition.tenant_id, "tenant")
        if not ref.startswith(f"integration:{tenant}:") or not ref.split(":")[-1]:
            raise ControlPlaneError("core_control_plane.byok_tenant_mismatch")
    else:
        raise ControlPlaneError("core_control_plane.credential_source_invalid")


def _validate_route(definition: RouteDefinition) -> None:
    _require_id(definition.policy_id, "policy")
    _require_id(definition.model_id, "model")
    _require_id(definition.price_snapshot_id, "price_snapshot")
    if definition.scope == "platform":
        if definition.tenant_id is not None or definition.unit_id is not None:
            raise ControlPlaneError("core_control_plane.platform_scope_invalid")
    elif definition.scope == "tenant":
        _require_id(definition.tenant_id, "tenant")
        if definition.unit_id is not None:
            raise ControlPlaneError("core_control_plane.tenant_scope_invalid")
    elif definition.scope == "unit":
        _require_id(definition.tenant_id, "tenant")
        _require_id(definition.unit_id, "unit")
    else:
        raise ControlPlaneError("core_control_plane.scope_invalid")
    if not isinstance(definition.capability, CapabilityIA):
        raise ControlPlaneError("core_control_plane.capability_invalid")
    if not 0 <= definition.priority <= 10_000:
        raise ControlPlaneError("core_control_plane.priority_invalid")
    if not 1 <= definition.timeout_seconds <= 120:
        raise ControlPlaneError("core_control_plane.timeout_invalid")
    _check_reference(definition)


class AIControlPlaneStore:
    """Servico de persistencia; somente chamada por fronteira administrativa confiavel."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def register_provider(self, *, provider_id: str, adapter: str, base_url: str) -> None:
        _require_id(provider_id, "provider")
        if adapter not in {"gemini", "openai_compatible"}:
            raise ControlPlaneError("core_control_plane.adapter_invalid")
        if not base_url.startswith("https://") or any(c in base_url for c in ("@", "#", "?")):
            raise ControlPlaneError("core_control_plane.base_url_invalid")
        with self._sessions.begin() as db:
            db.add(AIProvider(provider_id=provider_id, adapter=adapter, base_url=base_url))

    def register_model(self, *, model_id: str, provider_id: str, name: str) -> None:
        _require_id(model_id, "model")
        _require_id(name, "model_name")
        with self._sessions.begin() as db:
            if db.get(AIProvider, _require_id(provider_id, "provider")) is None:
                raise ControlPlaneError("core_control_plane.provider_missing")
            db.add(AIModel(model_id=model_id, provider_id=provider_id, model_name=name))

    def grant_capability(self, *, model_id: str, capability: CapabilityIA) -> None:
        if not isinstance(capability, CapabilityIA):
            raise ControlPlaneError("core_control_plane.capability_invalid")
        with self._sessions.begin() as db:
            if db.get(AIModel, model_id) is None:
                raise ControlPlaneError("core_control_plane.model_missing")
            db.add(AIModelCapability(model_id=model_id, capability=capability.value))

    def set_provider_health(self, *, provider_id: str, status: str, circuit: str) -> None:
        if status not in {"healthy", "degraded", "unavailable", "unknown"}:
            raise ControlPlaneError("core_control_plane.health_invalid")
        if circuit not in {"closed", "open", "half_open"}:
            raise ControlPlaneError("core_control_plane.circuit_invalid")
        with self._sessions.begin() as db:
            if db.get(AIProvider, provider_id) is None:
                raise ControlPlaneError("core_control_plane.provider_missing")
            item = db.get(AIProviderHealth, provider_id)
            if item is None:
                db.add(AIProviderHealth(provider_id=provider_id, status=status, circuit=circuit))
            else:
                item.status = status
                item.circuit = circuit

    def add_route(self, definition: RouteDefinition) -> None:
        _validate_route(definition)
        with self._sessions.begin() as db:
            model = db.get(AIModel, definition.model_id)
            if model is None:
                raise ControlPlaneError("core_control_plane.model_missing")
            capability = db.scalar(
                select(AIModelCapability.id).where(
                    AIModelCapability.model_id == definition.model_id,
                    AIModelCapability.capability == definition.capability.value,
                )
            )
            if capability is None:
                raise ControlPlaneError("core_control_plane.model_capability_missing")
            db.add(
                AIRoutePolicy(
                    policy_id=definition.policy_id,
                    scope=definition.scope,
                    tenant_id=definition.tenant_id,
                    unit_id=definition.unit_id,
                    model_id=definition.model_id,
                    capability=definition.capability.value,
                    priority=definition.priority,
                    price_snapshot_id=definition.price_snapshot_id,
                    credential_source=definition.credential_source,
                    secret_reference=definition.secret_reference,
                    timeout_seconds=definition.timeout_seconds,
                )
            )

    def resolve(
        self, *, tenant_id: str, unit_id: str, capability: CapabilityIA
    ) -> tuple[ResolvedCoreRoute, ...]:
        tenant_id = _require_id(tenant_id, "tenant")
        unit_id = _require_id(unit_id, "unit")
        if not isinstance(capability, CapabilityIA):
            raise ControlPlaneError("core_control_plane.capability_invalid")

        scopes = (("unit", tenant_id, unit_id), ("tenant", tenant_id, None), ("platform", None, None))
        with self._sessions() as db:
            for scope, tenant, unit in scopes:
                policies = db.scalars(
                    select(AIRoutePolicy).where(
                        AIRoutePolicy.scope == scope,
                        AIRoutePolicy.tenant_id == tenant,
                        AIRoutePolicy.unit_id == unit,
                        AIRoutePolicy.capability == capability.value,
                        AIRoutePolicy.enabled.is_(True),
                    )
                ).all()
                if not policies:
                    continue
                priorities = [p.priority for p in policies]
                if len(priorities) != len(set(priorities)):
                    raise ControlPlaneError("core_control_plane.ambiguous_priority")
                results: list[ResolvedCoreRoute] = []
                for policy in sorted(policies, key=lambda p: -p.priority):
                    model = db.get(AIModel, policy.model_id)
                    if model is None or not model.enabled:
                        continue
                    provider = db.get(AIProvider, model.provider_id)
                    health = db.get(AIProviderHealth, model.provider_id)
                    if (
                        provider is None
                        or not provider.enabled
                        or health is None
                        or health.status != "healthy"
                        or health.circuit != "closed"
                    ):
                        continue
                    results.append(
                        ResolvedCoreRoute(
                            route=RotaIA(
                                configuracao_id=policy.policy_id,
                                provider=provider.provider_id,
                                model=model.model_name,
                                capability=capability,
                                prioridade=policy.priority,
                                price_snapshot_id=policy.price_snapshot_id,
                            ),
                            scope=scope,
                            adapter=provider.adapter,
                            base_url=provider.base_url,
                            credential_source=policy.credential_source,
                            secret_reference=policy.secret_reference,
                            timeout_seconds=policy.timeout_seconds,
                        )
                    )
                if not results:
                    raise ControlPlaneError("core_control_plane.no_healthy_route")
                return tuple(results)
        raise ControlPlaneError("core_control_plane.no_route")
