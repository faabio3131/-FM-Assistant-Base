"""API interna do FM Core Base para consumidores como FM Assistant Base."""

from __future__ import annotations

import base64
import binascii
import hmac
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from core.ai_admin_read_api import register_admin_read_routes
from core.ai_assistant_credential_gateway import AssistantSignedCredentialGateway
from core.ai_control_plane import ControlPlaneError
from core.ai_control_plane_bootstrap import build_persistent_core, control_plane_is_ready
from core.ai_quota_store import QuotaDenied, QuotaReservations
from core.ai_router import FalhaRotaDefinitiva, FalhaRotaTransitoria, SemRotaCompativel
from core.ai_service_contracts import CoreAIResult, TextMessage
from core.ai_service_runtime import CoreAIRuntime
from core.ai_service_settings import CoreSettings, load_settings
from core.seguranca.erros import ReferenciaSegredoInvalida, SegredoAusente


class TextMessageRequest(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=50_000)


class TextAIRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)
    system_prompt: str = Field(min_length=1, max_length=50_000)
    messages: list[TextMessageRequest] = Field(min_length=1, max_length=100)


class AudioAIRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)
    mime_type: str = Field(pattern=r"^audio/")
    audio_base64: str = Field(min_length=1)
    instruction: str = Field(min_length=1, max_length=4_000)


class AIResponse(BaseModel):
    content: str
    provider: str
    model: str
    fallback_used: bool
    fallback_reason: str | None
    price_snapshot_id: str


def _response(result: CoreAIResult) -> AIResponse:
    return AIResponse(
        content=result.content,
        provider=result.provider,
        model=result.model,
        fallback_used=result.fallback_used,
        fallback_reason=result.fallback_reason,
        price_snapshot_id=result.price_snapshot_id,
    )


def create_app(
    settings: CoreSettings | None = None,
    runtime: CoreAIRuntime | None = None,
) -> FastAPI:
    cfg = (settings or load_settings()).validate()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = cfg
        db_engine = None
        if cfg.persistent_control_plane:
            tenant_gateway = (
                AssistantSignedCredentialGateway(
                    base_url=cfg.assistant_bridge_url or "",
                    key_id=cfg.assistant_bridge_key_id or "",
                    signing_key=cfg.assistant_bridge_signing_key or "",
                )
                if cfg.assistant_bridge_url
                else None
            )
            ai_runtime, db_engine = build_persistent_core(
                cfg.control_plane_database_url or "",
                tenant_gateway=tenant_gateway,
            )
        else:
            ai_runtime = runtime or CoreAIRuntime.from_settings(cfg)
        app.state.ai_runtime = ai_runtime
        app.state.control_plane_engine = db_engine
        try:
            yield
        finally:
            if db_engine is not None:
                db_engine.dispose()

    app = FastAPI(
        title="FM Core Base AI Service",
        version="0.1.0",
        description="Roteamento multimodelo e capacidades de IA da FM Tecnologia.",
        lifespan=lifespan,
    )

    def require_service_key(
        request: Request,
        x_core_service_key: str | None = Header(default=None, alias="X-Core-Service-Key"),
    ) -> None:
        expected = request.app.state.settings.service_key
        if not x_core_service_key or not hmac.compare_digest(expected, x_core_service_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="core_service_unauthorized",
            )

    @app.get("/health")
    def health() -> dict[str, object]:
        if cfg.persistent_control_plane:
            return {
                "status": "ok",
                "service": "fm-core-base",
                "mode": "control_plane",
            }
        return {
            "status": "ok",
            "service": "fm-core-base",
            "routes": len(cfg.routes),
            "providers": sorted({route.provider for route in cfg.routes}),
        }

    @app.get("/ready")
    def readiness(request: Request) -> dict[str, str]:
        engine = request.app.state.control_plane_engine
        if cfg.persistent_control_plane and (
            engine is None or not control_plane_is_ready(engine)
        ):
            raise HTTPException(status_code=503, detail="core_control_plane_not_ready")
        return {"status": "ready"}

    @app.post(
        "/v1/ai/text",
        response_model=AIResponse,
        dependencies=[Depends(require_service_key)],
    )
    def text_ai(payload: TextAIRequest, request: Request) -> AIResponse:
        try:
            result = request.app.state.ai_runtime.generate_text(
                tenant_id=payload.tenant_id,
                unit_id=payload.unit_id,
                request_id=payload.request_id,
                correlation_id=payload.correlation_id,
                system_prompt=payload.system_prompt,
                messages=tuple(
                    TextMessage(role=item.role, content=item.content)
                    for item in payload.messages
                ),
            )
        except (
            ControlPlaneError, SegredoAusente, ReferenciaSegredoInvalida, SQLAlchemyError
        ) as exc:
            raise HTTPException(
                status_code=503, detail="core_control_plane_dependency_unavailable"
            ) from exc
        except (SemRotaCompativel, FalhaRotaTransitoria) as exc:
            detail = (
                "core_control_plane_dependency_unavailable"
                if exc.codigo == "core_ai_credential_unavailable"
                else exc.codigo
            )
            raise HTTPException(status_code=503, detail=detail) from exc
        except FalhaRotaDefinitiva as exc:
            raise HTTPException(status_code=502, detail=exc.codigo) from exc
        return _response(result)

    @app.post(
        "/v1/ai/transcribe",
        response_model=AIResponse,
        dependencies=[Depends(require_service_key)],
    )
    def transcribe_ai(payload: AudioAIRequest, request: Request) -> AIResponse:
        try:
            audio = base64.b64decode(payload.audio_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=422, detail="audio_base64_invalid") from exc
        if not audio or len(audio) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="audio_size_invalid")
        try:
            result = request.app.state.ai_runtime.transcribe_audio(
                tenant_id=payload.tenant_id,
                unit_id=payload.unit_id,
                request_id=payload.request_id,
                correlation_id=payload.correlation_id,
                audio=audio,
                mime_type=payload.mime_type,
                instruction=payload.instruction,
            )
        except (
            ControlPlaneError, SegredoAusente, ReferenciaSegredoInvalida, SQLAlchemyError
        ) as exc:
            raise HTTPException(
                status_code=503, detail="core_control_plane_dependency_unavailable"
            ) from exc
        except (SemRotaCompativel, FalhaRotaTransitoria) as exc:
            detail = (
                "core_control_plane_dependency_unavailable"
                if exc.codigo == "core_ai_credential_unavailable"
                else exc.codigo
            )
            raise HTTPException(status_code=503, detail=detail) from exc
        except FalhaRotaDefinitiva as exc:
            raise HTTPException(status_code=502, detail=exc.codigo) from exc
        return _response(result)

    @app.get(
        "/v1/plan/usage", dependencies=[Depends(require_service_key)],
    )
    def read_plan_usage(
        request: Request,
        tenant_id: str = Query(min_length=1, max_length=128),
        unit_id: str = Query(min_length=1, max_length=128),
        resource: str = Query(min_length=1, max_length=80),
        scope: str = Query(pattern="^(tenant|unit)$"),
    ) -> dict[str, object]:
        """Exact-scoped read of committed quota ledger; no default zero."""
        engine = request.app.state.control_plane_engine
        if engine is None:
            raise HTTPException(status_code=503, detail="plan_usage_unavailable")
        try:
            ledger = QuotaReservations(sessionmaker(engine, expire_on_commit=False))
            scoped_unit = "__tenant__" if scope == "tenant" else unit_id
            snapshot = ledger.usage_snapshot(
                tenant_id=tenant_id, unit_id=scoped_unit,
                capability=resource, at=datetime.now(UTC),
            )
        except (QuotaDenied, SQLAlchemyError) as exc:
            raise HTTPException(
                status_code=503, detail="plan_usage_unavailable",
            ) from exc
        return {
            "tenant_id": tenant_id,
            "unit_id": unit_id,
            "resource": resource,
            "scope": scope,
            "policy_revision": snapshot.policy_revision,
            "limit_units": snapshot.limit_units,
            "window_seconds": snapshot.window_seconds,
            "consumed_units": snapshot.consumed_units,
            "reserved_units": snapshot.reserved_units,
            "remaining_units": snapshot.remaining_units,
            "period_ends_at": snapshot.period_ends_at.isoformat(),
            "observed_at": datetime.now(UTC).isoformat(),
        }

    register_admin_read_routes(app)
    return app
