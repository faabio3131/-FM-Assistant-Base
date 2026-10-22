"""API HTTP do FM Assistant Base SaaS."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, SecretStr, ValidationError

from .capabilities import KnowledgeCapabilityProvider
from .channels.evolution_events import EvolutionEventDenied, EvolutionEventVerifier
from .channels.whatsapp_evolution import EvolutionClient, EvolutionSettings, EvolutionUnavailable
from .channels.whatsapp_meta import WhatsAppProviderError
from .command_bridge_control_service import CommandBridgeControlService, CommandBridgeDenied
from .commercial_license_transition import (
    CommercialLicenseTransitionDenied,
    SignedCommercialLicenseTransition,
)
from .core_bridge_models import CoreBridgeAccessORM  # noqa: F401 - ORM registration
from .core_bridge_service import CoreBridgeDenied, CoreBridgeService
from .core_client import CoreAIClient, CoreAudioTranscriber
from .core_plan_usage_reader import CoreQuotaUsageHTTPReader
from .credential_vault import FernetCredentialVault
from .db import create_schema, create_session_factory
from .domain import AssistantPersona, Channel, Conversation, Message, TenantContext
from .evolution_native_ingress import EvolutionNativeIngress, NativeEvolutionDenied
from .evolution_onboarding import EvolutionOnboarding
from .evolution_queue import EvolutionInboundQueue, EvolutionQueueCapacityExceeded
from .evolution_runtime import EvolutionRuntime
from .gateways import CoreModelGateway, DevelopmentModelGateway, OpenAICompatibleGateway
from .identity import (
    MACHINE_PERMISSIONS,
    AuthContext,
    Permission,
    PrincipalKind,
    Role,
    can_assign_role,
    permissions_for_role,
)
from .identity_repository import IdentityRepository, SessionPrincipal
from .identity_service import IdentityService
from .integration import CredentialSource, IntegrationConnection
from .integration_repository import IntegrationRepository
from .integration_service import IntegrationService
from .knowledge_retrieval import BoundedKnowledgeRetrieval
from .knowledge_versioning import KnowledgeVersionDenied, VersionedKnowledgeIngestion
from .license_security_hold import LicenseSecurityHoldDenied, SignedLicenseSecurityHold
from .plan_consumption_dashboard import render_consumption_dashboard
from .plan_consumption_view import PlanConsumptionView
from .plan_license_binding import GovernedPlanLicenseBinding, PlanLicenseBindingDenied
from .plan_limits import PlanLimitDenied
from .plan_policy_manifest import authenticated_core_plan_grant
from .plan_sync_service import CommandPlanProjectionService, PlanSyncDenied
from .qr_onboarding_page import render_qr_page
from .qr_policy_sync import CommandQrDisplayPolicyService, QrDisplayPolicyDenied
from .repositories import (
    ConversationSQLAlchemyRepository,
    CredentialRepository,
    KnowledgeRepository,
    PersonaSQLAlchemyRepository,
    SQLAuditSink,
)
from .security import generate_api_key, hash_api_key
from .service import AssistantService
from .settings import Settings, load_settings
from .whatsapp_repository import WhatsAppChannelRepository, WhatsAppInboundRepository
from .whatsapp_runtime import WhatsAppRuntime


class ProvisionCredentialRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)


class ProvisionCredentialResponse(BaseModel):
    credential_id: str
    tenant_id: str
    unit_id: str
    api_key: str


class PersonaRequest(BaseModel):
    public_name: str = Field(min_length=1, max_length=160)
    language: str = Field(default="pt-BR", min_length=2, max_length=32)
    tone: str = Field(default="profissional", min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=12000)
    enabled: bool = True


class PersonaResponse(BaseModel):
    public_name: str
    language: str
    tone: str
    instructions: str
    enabled: bool


class KnowledgeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=100_000)


class KnowledgeResponse(BaseModel):
    document_id: str


class KnowledgeVersionRequest(BaseModel):
    expected_revision: int = Field(strict=True, ge=0, le=2_000_000_000)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=24_000)


class KnowledgeVersionResponse(BaseModel):
    document_id: str
    revision: int
    chunks: int
    content_sha256: str
    indexed: bool
    external_source_verified: bool


class ConversationRequest(BaseModel):
    channel: Channel = Channel.API
    external_ref: str | None = Field(default=None, max_length=255)


class ConversationResponse(BaseModel):
    conversation_id: str
    channel: Channel
    status: str
    external_ref: str | None


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str


class HandoffRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)




class CommandBridgeManagePayload(BaseModel):
    action: str = Field(pattern=r"^(provision|grant|revoke_grant|revoke_identity)$")
    tenant_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)
    capability: str = Field(min_length=1, max_length=160)
    target_key_id: str = Field(min_length=1, max_length=64)
    actor_user_id: str = Field(min_length=1, max_length=128)
    organization_id: str = Field(min_length=1, max_length=128)
    step_up_at: int
    command_request_id: str = Field(min_length=1, max_length=96)


class PlanSyncAllowance(BaseModel):
    model_config = {"extra": "forbid"}

    resource: str
    scope: str
    limitUnits: int
    windowSeconds: int


class PlanLicenseBindPayload(BaseModel):
    model_config = {"extra": "forbid"}

    product_code: str = Field(pattern=r"^VENDEATENDEIA$")
    organization_id: str = Field(min_length=1, max_length=128)
    actor_user_id: str = Field(min_length=1, max_length=128)
    approved_at: int
    tenant_id: str = Field(min_length=1, max_length=128)
    plan_code: str = Field(min_length=2, max_length=120)
    plan_revision: int = Field(gt=0)


class PlanBindingStatusPayload(BaseModel):
    model_config = {"extra": "forbid"}

    product_code: str = Field(pattern=r"^VENDEATENDEIA$")
    organization_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    plan_code: str = Field(min_length=2, max_length=120)
    plan_revision: int = Field(gt=0)
    operation_nonce: str = Field(min_length=22, max_length=96)


class CommandCommercialStatusPayload(BaseModel):
    """Exact authenticated FM read-back, no external authorization."""
    model_config = {"extra": "forbid"}

    product_code: str = Field(pattern=r"^VENDEATENDEIA$")
    organization_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    command_request_id: str = Field(min_length=1, max_length=128)


class CommandCommercialTransitionPayload(BaseModel):
    """Strict internal FM-only entitlement lifecycle; no client token access."""

    model_config = {"extra": "forbid"}

    product_code: str = Field(pattern=r"^VENDEATENDEIA$")
    organization_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    actor_user_id: str = Field(min_length=1, max_length=128)
    command_request_id: str = Field(min_length=1, max_length=128)
    approved_at: int = Field(strict=True)
    action: str = Field(pattern=r"^(SUSPEND_DELINQUENCY|REACTIVATE_VERIFIED|RENEW_VERIFIED|APPLY_UPGRADE|APPLY_DOWNGRADE|CANCEL_AT_PERIOD_END)$")
    expected_status: str = Field(pattern=r"^(active|trial|suspended)$")
    expected_plan_code: str = Field(min_length=1, max_length=120)
    expected_plan_revision: int = Field(strict=True, gt=0)
    expected_valid_until: int = Field(strict=True, gt=0)
    target_plan_code: str = Field(min_length=1, max_length=120)
    target_plan_revision: int = Field(strict=True, gt=0)
    target_valid_until: int = Field(strict=True, gt=0)
    effective_at: int = Field(strict=True, gt=0)
    verified_payment_ref: str = Field(min_length=1, max_length=128)


class CommandLicenseSecurityHoldPayload(BaseModel):
    """Strict server-only revocation; never accepts financial changes."""
    model_config = {"extra": "forbid"}

    product_code: str = Field(pattern=r"^VENDEATENDEIA$")
    organization_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    actor_user_id: str = Field(min_length=1, max_length=128)
    command_request_id: str = Field(min_length=1, max_length=128)
    approved_at: int = Field(strict=True)
    step_up_at: int = Field(strict=True)
    plan_code: str = Field(min_length=1, max_length=120)
    plan_revision: int = Field(strict=True, ge=1)
    expected_valid_until: int = Field(strict=True, ge=1)
    reason: str = Field(pattern=r"^security_hold$")


class CommandQrDisplayPolicyPayload(BaseModel):
    model_config = {"extra": "forbid"}

    product_code: str = Field(pattern=r"^VENDEATENDEIA$")
    organization_id: str = Field(min_length=1, max_length=128)
    actor_user_id: str = Field(min_length=1, max_length=128)
    approved_at: int = Field(strict=True)
    revision: int = Field(gt=0, strict=True)
    display_seconds: int = Field(ge=15, le=120, strict=True)


class CommandPlanProjectionPayload(BaseModel):
    model_config = {"extra": "forbid"}

    product_code: str = Field(pattern=r"^VENDEATENDEIA$")
    organization_id: str = Field(min_length=1, max_length=128)
    actor_user_id: str = Field(min_length=1, max_length=128)
    approved_at: int
    plan_code: str = Field(min_length=2, max_length=120)
    revision: int = Field(gt=0)
    label: str = Field(min_length=2, max_length=160)
    allowances: list[PlanSyncAllowance] = Field(min_length=1, max_length=32)


class CoreBridgeResolvePayload(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)
    capability: str = Field(min_length=1, max_length=160)
    connection_id: str = Field(min_length=1, max_length=64)

SESSION_COOKIE_NAME = "fm_assistant_session"


class BootstrapTenantOwnerRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    tenant_name: str = Field(min_length=1, max_length=255)
    unit_id: str = Field(min_length=1, max_length=128)
    unit_name: str = Field(min_length=1, max_length=255)
    owner_email: str = Field(min_length=3, max_length=320)
    owner_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    plan_code: str = Field(default="trial", min_length=1, max_length=120)
    trial_days: int = Field(default=14, ge=0, le=90)


class BootstrapTenantOwnerResponse(BaseModel):
    tenant_id: str
    unit_id: str
    user_id: str
    membership_id: str


class LoginRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    unit_id: str | None = Field(default=None, max_length=128)


class SessionResponse(BaseModel):
    user_id: str
    tenant_id: str
    unit_id: str
    role: Role
    email: str
    display_name: str
    permissions: list[str]


class SwitchUnitRequest(BaseModel):
    unit_id: str = Field(min_length=1, max_length=128)


class UnitCreateRequest(BaseModel):
    unit_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)


class UnitResponse(BaseModel):
    unit_id: str
    display_name: str


class InvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Role
    unit_id: str = Field(min_length=1, max_length=128)
    expires_hours: int = Field(default=72, ge=1, le=168)


class InvitationResponse(BaseModel):
    invitation_id: str
    invitation_token: str


class InvitationAcceptRequest(BaseModel):
    invitation_token: str = Field(min_length=10, max_length=512)
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=256)


class InvitationAcceptResponse(BaseModel):
    user_id: str


class RecoveryRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)


class RecoveryRequestResponse(BaseModel):
    accepted: bool = True
    recovery_token: str | None = None


class RecoveryCompleteRequest(BaseModel):
    recovery_token: str = Field(min_length=10, max_length=512)
    new_password: str = Field(min_length=12, max_length=256)


class EntitlementResponse(BaseModel):
    capability: str
    enabled: bool
    limit_value: int | None


class IntegrationConnectRequest(BaseModel):
    provider_key: str = Field(min_length=1, max_length=120)
    config: dict[str, str | None] = Field(default_factory=dict)
    secrets: dict[str, SecretStr]
    source: CredentialSource = CredentialSource.TENANT_MANAGED


class IntegrationConfigRequest(BaseModel):
    config: dict[str, str | None]


class IntegrationRotateRequest(BaseModel):
    secrets: dict[str, SecretStr]
    source: CredentialSource = CredentialSource.TENANT_MANAGED


class IntegrationProviderResponse(BaseModel):
    provider_key: str
    integration_type: str
    display_name: str
    definition_version: int
    config_fields: list[str]
    required_config_fields: list[str]
    secret_fields: list[str]
    capabilities: list[str]


class IntegrationResponse(BaseModel):
    connection_id: str
    provider_key: str
    integration_type: str
    status: str
    config: dict[str, str | None]
    revision: int
    capabilities: list[str]


class IntegrationValidationResponse(BaseModel):
    validation_id: str
    connection_id: str
    revision: int
    success: bool
    code: str


class IntegrationSecretMetadataResponse(BaseModel):
    secret_name: str
    version: int
    source: str
    storage_backend: str
    active: bool
    expires_at: str | None
    revoked_at: str | None


class EvolutionEvidenceInvestigationRequest(BaseModel):
    operation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    provider_reference: str = Field(
        min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$",
    )


class QRConnectionResponse(BaseModel):
    connection_id: str
    status: str
    qr_data_url: str | None = None


class WhatsAppChannelRequest(BaseModel):
    phone_number_id: str = Field(min_length=1, max_length=128)
    business_account_id: str | None = Field(default=None, max_length=128)
    access_token: SecretStr
    app_secret: SecretStr
    verify_token: SecretStr
    graph_api_version: str = Field(default="v23.0", pattern=r"^v\d+\.\d+$")


class WhatsAppChannelResponse(BaseModel):
    channel_id: str
    phone_number_id: str
    business_account_id: str | None
    graph_api_version: str
    webhook_path: str


def _integration_response(connection: IntegrationConnection) -> IntegrationResponse:
    return IntegrationResponse(
        connection_id=connection.connection_id,
        provider_key=connection.provider_key,
        integration_type=connection.integration_type,
        status=connection.status.value,
        config=connection.config,
        revision=connection.revision,
        capabilities=list(connection.capabilities),
    )


def _persona_response(persona: AssistantPersona) -> PersonaResponse:
    return PersonaResponse(
        public_name=persona.public_name,
        language=persona.language,
        tone=persona.tone,
        instructions=persona.instructions,
        enabled=persona.enabled,
    )


def _conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        channel=conversation.channel,
        status=conversation.status.value,
        external_ref=conversation.external_ref,
    )


def _message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        message_id=message.message_id,
        role=message.role.value,
        content=message.content,
    )


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_bearer_token")
    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_bearer_token")
    return token


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or load_settings()
    engine, session_factory = create_session_factory(cfg.database_url)

    credentials = CredentialRepository(session_factory)
    identity_repository = IdentityRepository(session_factory)
    identity_service = IdentityService(
        repository=identity_repository,
        session_pepper=cfg.session_pepper,
        session_ttl_minutes=cfg.session_ttl_minutes,
    )
    personas = PersonaSQLAlchemyRepository(session_factory)
    conversations = ConversationSQLAlchemyRepository(session_factory)
    knowledge = KnowledgeRepository(session_factory)
    knowledge_versioning = VersionedKnowledgeIngestion(session_factory)
    audit = SQLAuditSink(session_factory)

    audio_transcriber = None
    backend = cfg.model_backend.casefold()
    if backend == "core":
        assert cfg.core_base_url is not None
        assert cfg.core_service_key is not None
        core_client = CoreAIClient(
            base_url=cfg.core_base_url,
            service_key=cfg.core_service_key,
        )
        model = CoreModelGateway(core_client)
        audio_transcriber = CoreAudioTranscriber(core_client)
    elif backend == "openai_compatible":
        assert cfg.model_base_url is not None
        assert cfg.model_api_key is not None
        assert cfg.model_name is not None
        model = OpenAICompatibleGateway(
            base_url=cfg.model_base_url,
            api_key=cfg.model_api_key,
            model=cfg.model_name,
        )
    else:
        model = DevelopmentModelGateway()

    service = AssistantService(
        personas=personas,
        conversations=conversations,
        model=model,
        capabilities=KnowledgeCapabilityProvider(
            knowledge,
            retrieval=BoundedKnowledgeRetrieval(session_factory),
            retrieval_enabled=os.environ.get(
                "FM_ASSISTANT_KNOWLEDGE_CONTEXT_PACK_ENABLED", "false"
            ).casefold() == "true",
        ),
        audit=audit,
    )

    integration_repository = IntegrationRepository(session_factory)
    vault = FernetCredentialVault(cfg.channel_encryption_key)
    integration_service = IntegrationService(
        repository=integration_repository,
        vault=vault,
    )
    evolution_onboarding = (
        EvolutionOnboarding(
            repository=integration_repository,
            vault=vault,
            transport=EvolutionClient(EvolutionSettings(
                origin=cfg.evolution_origin,
                global_key=cfg.evolution_global_key,
            )),
            native_webhook_base_url=cfg.evolution_native_webhook_base_url,
        )
        if cfg.evolution_origin and cfg.evolution_global_key else None
    )
    evolution_runtime = (
        EvolutionRuntime(
            integrations=integration_repository,
            inbox=WhatsAppInboundRepository(session_factory),
            assistant=service,
            vault=vault,
            transport=evolution_onboarding._transport,
            verifier=EvolutionEventVerifier(
                signing_key=cfg.evolution_webhook_signing_key,
            ),
            sender_pepper=cfg.credential_pepper,
            queue=EvolutionInboundQueue(
                session_factory, vault,
                max_pending_per_connection=cfg.evolution_max_pending_per_connection,
            ),
        )
        if evolution_onboarding is not None and cfg.evolution_webhook_signing_key
        else None
    )
    evolution_native_ingress = (
        EvolutionNativeIngress(
            repository=integration_repository, vault=vault,
            runtime=evolution_runtime,
            internal_signer=cfg.evolution_webhook_signing_key,
        )
        if evolution_runtime is not None and cfg.evolution_native_webhook_base_url
        else None
    )
    core_bridge = CoreBridgeService(
        sessions=session_factory,
        vault=vault,
        key_id=cfg.core_bridge_key_id,
        signing_key=cfg.core_bridge_signing_key,
    )
    command_bridge = CommandBridgeControlService(
        sessions=session_factory,
        command_key_id=cfg.command_control_key_id,
        command_signing_key=cfg.command_control_signing_key,
        trusted_organization=cfg.trusted_command_organization_id,
        core_key_id=cfg.core_bridge_key_id,
    )
    plan_projection = CommandPlanProjectionService(
        sessions=session_factory,
        key_id=cfg.command_control_key_id,
        signing_key=cfg.command_control_signing_key,
        trusted_organization=cfg.trusted_command_organization_id,
    )
    qr_display_policy = CommandQrDisplayPolicyService(
        sessions=session_factory,
        key_id=cfg.command_control_key_id,
        signing_key=cfg.command_control_signing_key,
        trusted_organization=cfg.trusted_command_organization_id,
    )
    commercial_license_transition = SignedCommercialLicenseTransition(
        sessions=session_factory,
        key_id=cfg.command_control_key_id,
        signing_key=cfg.command_control_signing_key,
        trusted_organization=cfg.trusted_command_organization_id,
    )
    license_security_hold = SignedLicenseSecurityHold(
        sessions=session_factory,
        key_id=cfg.command_control_key_id,
        signing_key=cfg.command_control_signing_key,
        trusted_organization=cfg.trusted_command_organization_id,
    )
    plan_license_binding = GovernedPlanLicenseBinding(
        sessions=session_factory,
        key_id=cfg.command_control_key_id,
        signing_key=cfg.command_control_signing_key,
        trusted_organization=cfg.trusted_command_organization_id,
    )
    consumption_view = PlanConsumptionView(
        session_factory,
        reader=(
            CoreQuotaUsageHTTPReader(
                core_origin=cfg.core_base_url,
                service_key=cfg.core_service_key,
            )
            if backend == "core" and cfg.core_base_url and cfg.core_service_key
            else None
        ),
    )
    whatsapp_channels = WhatsAppChannelRepository(integration_service)
    whatsapp_inbound = WhatsAppInboundRepository(session_factory)
    whatsapp_runtime = WhatsAppRuntime(
        channels=whatsapp_channels,
        inbound=whatsapp_inbound,
        assistant=service,
        sender_pepper=cfg.credential_pepper,
        audio_transcriber=audio_transcriber,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if cfg.auto_create_schema:
            create_schema(engine)
        integration_service.ensure_catalog()
        app.state.settings = cfg
        app.state.credentials = credentials
        app.state.identity_repository = identity_repository
        app.state.identity_service = identity_service
        app.state.knowledge = knowledge
        app.state.knowledge_versioning = knowledge_versioning
        app.state.assistant_service = service
        app.state.integration_repository = integration_repository
        app.state.integration_service = integration_service
        app.state.evolution_onboarding = evolution_onboarding
        app.state.evolution_runtime = evolution_runtime
        app.state.evolution_native_ingress = evolution_native_ingress
        app.state.whatsapp_channels = whatsapp_channels
        app.state.whatsapp_runtime = whatsapp_runtime
        yield
        engine.dispose()

    app = FastAPI(
        title="FM Assistant Base",
        version="0.1.0",
        description="Base SaaS multi-tenant para agentes de atendimento.",
        lifespan=lifespan,
    )

    def current_session(
        request: Request,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> SessionPrincipal:
        if not session_token:
            raise HTTPException(status_code=401, detail="session_required")
        principal = request.app.state.identity_service.resolve(session_token)
        if principal is None:
            raise HTTPException(status_code=401, detail="session_invalid")
        return principal

    def human_permission(permission: Permission):
        def dependency(
            principal: SessionPrincipal = Depends(current_session),
        ) -> SessionPrincipal:
            if permission not in permissions_for_role(principal.role):
                raise HTTPException(status_code=403, detail="permission_forbidden")
            return principal

        return dependency

    def auth_context(
        request: Request,
        authorization: str | None = Header(default=None),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> AuthContext:
        if session_token:
            principal = request.app.state.identity_service.resolve(session_token)
            if principal is None:
                raise HTTPException(status_code=401, detail="session_invalid")
            return AuthContext(
                tenant=TenantContext(
                    tenant_id=principal.tenant_id,
                    unit_id=principal.unit_id,
                    credential_id=f"user:{principal.user_id}",
                ),
                actor_id=principal.user_id,
                kind=PrincipalKind.USER,
                permissions=permissions_for_role(principal.role),
                role=principal.role,
                user_id=principal.user_id,
                session_id=principal.session_id,
            )

        token = _bearer_token(authorization)
        key_hash = hash_api_key(token, request.app.state.settings.credential_pepper)
        credential = request.app.state.credentials.resolve_hash(key_hash)
        if credential is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="credential_not_found",
            )
        return AuthContext(
            tenant=credential.context(),
            actor_id=credential.credential_id,
            kind=PrincipalKind.API_CREDENTIAL,
            permissions=MACHINE_PERMISSIONS,
        )

    def tenant_with_permission(permission: Permission):
        def dependency(auth: AuthContext = Depends(auth_context)) -> TenantContext:
            try:
                auth.require(permission)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail="permission_forbidden") from exc
            return auth.tenant

        return dependency

    def require_admin(
        request: Request,
        x_admin_key: str | None = Header(default=None),
    ) -> None:
        if x_admin_key != request.app.state.settings.admin_key:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_forbidden")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "fm-assistant-base"}

    @app.post(
        "/v1/bootstrap/tenant-owner",
        response_model=BootstrapTenantOwnerResponse,
        dependencies=[Depends(require_admin)],
    )
    def bootstrap_tenant_owner(
        payload: BootstrapTenantOwnerRequest,
        request: Request,
    ) -> BootstrapTenantOwnerResponse:
        try:
            user_id, membership_id = request.app.state.identity_service.bootstrap_owner(
                tenant_id=payload.tenant_id,
                tenant_name=payload.tenant_name,
                unit_id=payload.unit_id,
                unit_name=payload.unit_name,
                owner_email=payload.owner_email,
                owner_name=payload.owner_name,
                password=payload.password,
                plan_code=payload.plan_code,
                trial_days=payload.trial_days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return BootstrapTenantOwnerResponse(
            tenant_id=payload.tenant_id.strip(),
            unit_id=payload.unit_id.strip(),
            user_id=user_id,
            membership_id=membership_id,
        )

    @app.post("/v1/auth/login", response_model=SessionResponse)
    def login(
        payload: LoginRequest,
        response: Response,
        request: Request,
    ) -> SessionResponse:
        try:
            result = request.app.state.identity_service.login(
                email=payload.email,
                password=payload.password,
                tenant_id=payload.tenant_id,
                unit_id=payload.unit_id,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=result.token,
            max_age=request.app.state.settings.session_ttl_minutes * 60,
            httponly=True,
            secure=request.app.state.settings.production_like,
            samesite="strict",
            path="/",
        )
        permissions = sorted(
            permission.value for permission in permissions_for_role(result.principal.role)
        )
        return SessionResponse(
            user_id=result.principal.user_id,
            tenant_id=result.principal.tenant_id,
            unit_id=result.principal.unit_id,
            role=result.principal.role,
            email=result.principal.email,
            display_name=result.principal.display_name,
            permissions=permissions,
        )

    @app.post("/v1/auth/logout", status_code=204)
    def logout(
        response: Response,
        request: Request,
        principal: SessionPrincipal = Depends(current_session),
    ) -> Response:
        request.app.state.identity_service.logout(principal)
        response.delete_cookie(SESSION_COOKIE_NAME, path="/", samesite="strict")
        response.status_code = 204
        return response

    @app.get("/v1/auth/me", response_model=SessionResponse)
    def me(
        principal: SessionPrincipal = Depends(current_session),
    ) -> SessionResponse:
        return SessionResponse(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            unit_id=principal.unit_id,
            role=principal.role,
            email=principal.email,
            display_name=principal.display_name,
            permissions=sorted(
                permission.value for permission in permissions_for_role(principal.role)
            ),
        )

    @app.post("/v1/auth/switch-unit", response_model=SessionResponse)
    def switch_unit(
        payload: SwitchUnitRequest,
        request: Request,
        principal: SessionPrincipal = Depends(current_session),
    ) -> SessionResponse:
        try:
            switched = request.app.state.identity_service.switch_unit(
                principal,
                unit_id=payload.unit_id,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return SessionResponse(
            user_id=switched.user_id,
            tenant_id=switched.tenant_id,
            unit_id=switched.unit_id,
            role=switched.role,
            email=switched.email,
            display_name=switched.display_name,
            permissions=sorted(
                permission.value for permission in permissions_for_role(switched.role)
            ),
        )

    @app.get("/v1/units", response_model=list[UnitResponse])
    def list_units(
        request: Request,
        principal: SessionPrincipal = Depends(human_permission(Permission.UNIT_READ)),
    ) -> list[UnitResponse]:
        rows = request.app.state.identity_repository.list_units(
            tenant_id=principal.tenant_id,
            membership_id=principal.membership_id,
        )
        return [UnitResponse(unit_id=unit_id, display_name=name) for unit_id, name in rows]

    @app.post("/v1/units", response_model=UnitResponse)
    def create_unit(
        payload: UnitCreateRequest,
        request: Request,
        principal: SessionPrincipal = Depends(human_permission(Permission.UNIT_MANAGE)),
    ) -> UnitResponse:
        try:
            request.app.state.identity_repository.create_unit(
                tenant_id=principal.tenant_id,
                membership_id=principal.membership_id,
                unit_id=payload.unit_id.strip(),
                display_name=payload.display_name.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return UnitResponse(
            unit_id=payload.unit_id.strip(),
            display_name=payload.display_name.strip(),
        )

    @app.post("/v1/users/invitations", response_model=InvitationResponse)
    def create_invitation(
        payload: InvitationRequest,
        request: Request,
        principal: SessionPrincipal = Depends(human_permission(Permission.USER_INVITE)),
    ) -> InvitationResponse:
        if not can_assign_role(principal.role, payload.role):
            raise HTTPException(status_code=403, detail="role_assignment_forbidden")
        try:
            invitation_id, token = request.app.state.identity_service.create_invitation(
                tenant_id=principal.tenant_id,
                unit_id=payload.unit_id,
                email=payload.email,
                role=payload.role,
                expires_hours=payload.expires_hours,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return InvitationResponse(
            invitation_id=invitation_id,
            invitation_token=token,
        )

    @app.post("/v1/auth/accept-invitation", response_model=InvitationAcceptResponse)
    def accept_invitation(
        payload: InvitationAcceptRequest,
        request: Request,
    ) -> InvitationAcceptResponse:
        try:
            user_id = request.app.state.identity_service.accept_invitation(
                token=payload.invitation_token,
                display_name=payload.display_name,
                password=payload.password,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return InvitationAcceptResponse(user_id=user_id)

    @app.post(
        "/v1/auth/recovery/request",
        response_model=RecoveryRequestResponse,
        status_code=202,
    )
    def request_recovery(
        payload: RecoveryRequest,
        request: Request,
    ) -> RecoveryRequestResponse:
        token = request.app.state.identity_service.request_password_reset(
            tenant_id=payload.tenant_id,
            email=payload.email,
        )
        exposed = token if not request.app.state.settings.production_like else None
        return RecoveryRequestResponse(accepted=True, recovery_token=exposed)

    @app.post("/v1/auth/recovery/complete", status_code=204)
    def complete_recovery(
        payload: RecoveryCompleteRequest,
        request: Request,
    ) -> Response:
        try:
            completed = request.app.state.identity_service.complete_password_reset(
                token=payload.recovery_token,
                new_password=payload.new_password,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not completed:
            raise HTTPException(status_code=400, detail="recovery_token_invalid")
        return Response(status_code=204)

    @app.get("/v1/entitlements", response_model=list[EntitlementResponse])
    def list_entitlements(
        request: Request,
        principal: SessionPrincipal = Depends(human_permission(Permission.BILLING_READ)),
    ) -> list[EntitlementResponse]:
        rows = request.app.state.identity_repository.entitlements(
            tenant_id=principal.tenant_id,
        )
        return [
            EntitlementResponse(
                capability=capability,
                enabled=enabled,
                limit_value=limit_value,
            )
            for capability, enabled, limit_value in rows
        ]

    @app.get("/v1/plan/consumption")
    def customer_plan_consumption(
        principal: SessionPrincipal = Depends(human_permission(Permission.BILLING_READ)),
    ) -> JSONResponse:
        """Only the authenticated tenant/unit; NEVER accept scope from query."""
        try:
            view = consumption_view.get(
                tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                now=datetime.now(UTC),
            )
        except PlanLimitDenied as exc:
            raise HTTPException(status_code=403, detail="plan_unavailable") from exc
        return JSONResponse(view, headers={"Cache-Control": "no-store"})

    @app.get("/v1/plan/consumption/dashboard", response_class=HTMLResponse)
    def customer_plan_dashboard(
        principal: SessionPrincipal = Depends(human_permission(Permission.BILLING_READ)),
    ) -> HTMLResponse:
        try:
            data = consumption_view.get(
                tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                now=datetime.now(UTC),
            )
        except PlanLimitDenied as exc:
            raise HTTPException(status_code=403, detail="plan_unavailable") from exc
        return HTMLResponse(
            render_consumption_dashboard(data),
            headers={"Cache-Control": "no-store",
                     "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
                     "X-Content-Type-Options": "nosniff"},
        )

    @app.post("/v1/api-credentials", response_model=ProvisionCredentialResponse)
    def create_api_credential(
        request: Request,
        principal: SessionPrincipal = Depends(
            human_permission(Permission.API_CREDENTIAL_MANAGE)
        ),
    ) -> ProvisionCredentialResponse:
        api_key = generate_api_key()
        credential_id = str(uuid4())
        context = TenantContext(
            tenant_id=principal.tenant_id,
            unit_id=principal.unit_id,
            credential_id=f"user:{principal.user_id}",
        )
        credential = request.app.state.credentials.create(
            tenant_id=context.tenant_id,
            unit_id=context.unit_id,
            credential_id=credential_id,
            key_hash=hash_api_key(api_key, request.app.state.settings.credential_pepper),
        )
        return ProvisionCredentialResponse(
            credential_id=credential.credential_id,
            tenant_id=credential.tenant_id,
            unit_id=credential.unit_id,
            api_key=api_key,
        )

    @app.delete("/v1/api-credentials/{credential_id}", status_code=204)
    def revoke_api_credential(
        credential_id: str,
        request: Request,
        principal: SessionPrincipal = Depends(
            human_permission(Permission.API_CREDENTIAL_MANAGE)
        ),
    ) -> Response:
        context = TenantContext(
            tenant_id=principal.tenant_id,
            unit_id=principal.unit_id,
            credential_id=f"user:{principal.user_id}",
        )
        if not request.app.state.credentials.revoke_scoped(context, credential_id):
            raise HTTPException(status_code=404, detail="credential_not_found")
        return Response(status_code=204)

    @app.post(
        "/v1/admin/credentials",
        response_model=ProvisionCredentialResponse,
        dependencies=[Depends(require_admin)],
    )
    def provision_credential(
        payload: ProvisionCredentialRequest,
        request: Request,
    ) -> ProvisionCredentialResponse:
        if request.app.state.settings.production_like:
            raise HTTPException(status_code=404, detail="legacy_admin_endpoint_disabled")
        request.app.state.identity_repository.ensure_scope(
            tenant_id=payload.tenant_id.strip(),
            unit_id=payload.unit_id.strip(),
        )
        api_key = generate_api_key()
        credential_id = str(uuid4())
        request.app.state.credentials.create(
            tenant_id=payload.tenant_id.strip(),
            unit_id=payload.unit_id.strip(),
            credential_id=credential_id,
            key_hash=hash_api_key(api_key, request.app.state.settings.credential_pepper),
        )
        return ProvisionCredentialResponse(
            credential_id=credential_id,
            tenant_id=payload.tenant_id.strip(),
            unit_id=payload.unit_id.strip(),
            api_key=api_key,
        )

    @app.delete(
        "/v1/admin/credentials/{credential_id}",
        status_code=204,
        dependencies=[Depends(require_admin)],
    )
    def revoke_credential(
        credential_id: str,
        request: Request,
    ) -> None:
        if request.app.state.settings.production_like:
            raise HTTPException(status_code=404, detail="legacy_admin_endpoint_disabled")
        revoked = request.app.state.credentials.revoke(credential_id)
        if not revoked:
            raise HTTPException(status_code=404, detail="credential_not_found")

    @app.get("/v1/persona", response_model=PersonaResponse)
    def get_persona(
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.PERSONA_READ)),
    ) -> PersonaResponse:
        persona = request.app.state.assistant_service.get_persona(context)
        if persona is None:
            raise HTTPException(status_code=404, detail="persona_not_found")
        return _persona_response(persona)

    @app.put("/v1/persona", response_model=PersonaResponse)
    def put_persona(
        payload: PersonaRequest,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.PERSONA_MANAGE)),
    ) -> PersonaResponse:
        persona = request.app.state.assistant_service.configure_persona(
            context=context,
            public_name=payload.public_name,
            language=payload.language,
            tone=payload.tone,
            instructions=payload.instructions,
            enabled=payload.enabled,
        )
        return _persona_response(persona)

    @app.post("/v1/knowledge", response_model=KnowledgeResponse)
    def add_knowledge(
        payload: KnowledgeRequest,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.KNOWLEDGE_MANAGE)),
    ) -> KnowledgeResponse:
        document_id = request.app.state.knowledge.add(
            context,
            title=payload.title,
            content=payload.content,
        )
        return KnowledgeResponse(document_id=document_id)

    @app.put("/v1/knowledge/{document_id}/version", response_model=KnowledgeVersionResponse)
    def version_knowledge_text(
        document_id: str,
        payload: KnowledgeVersionRequest,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.KNOWLEDGE_MANAGE)),
    ) -> KnowledgeVersionResponse:
        if os.environ.get("FM_ASSISTANT_KNOWLEDGE_VERSIONING_ENABLED", "false").casefold() != "true":
            raise HTTPException(status_code=503, detail="knowledge_versioning_not_configured")
        try:
            result = request.app.state.knowledge_versioning.index_text(
                context, document_id=document_id,
                expected_revision=payload.expected_revision,
                title=payload.title, content=payload.content,
            )
        except KnowledgeVersionDenied as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return KnowledgeVersionResponse(
            document_id=result.document_id, revision=result.revision,
            chunks=result.chunks, content_sha256=result.content_sha256,
            indexed=result.indexed,
            external_source_verified=result.external_source_verified,
        )

    @app.delete("/v1/knowledge/{document_id}", status_code=204)
    def deactivate_knowledge(
        document_id: str,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.KNOWLEDGE_MANAGE)),
    ) -> Response:
        # Scope is resolved from the authenticated principal, never an ID/header
        # provided by the caller. Foreign/missing IDs are indistinguishable.
        if not request.app.state.knowledge.deactivate(context, document_id):
            raise HTTPException(status_code=404, detail="knowledge_not_found")
        return Response(status_code=204)

    @app.post("/v1/conversations", response_model=ConversationResponse)
    def create_conversation(
        payload: ConversationRequest,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.CONVERSATION_RESPOND)),
    ) -> ConversationResponse:
        try:
            conversation = request.app.state.assistant_service.create_conversation(
                context=context,
                channel=payload.channel,
                external_ref=payload.external_ref,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _conversation_response(conversation)

    @app.get("/v1/conversations/{conversation_id}", response_model=ConversationResponse)
    def get_conversation(
        conversation_id: str,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.CONVERSATION_READ)),
    ) -> ConversationResponse:
        try:
            conversation = request.app.state.assistant_service.get_conversation(
                context=context,
                conversation_id=conversation_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="conversation_not_found") from exc
        return _conversation_response(conversation)

    @app.post(
        "/v1/conversations/{conversation_id}/messages",
        response_model=MessageResponse,
    )
    def send_message(
        conversation_id: str,
        payload: MessageRequest,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.CONVERSATION_RESPOND)),
    ) -> MessageResponse:
        try:
            message = request.app.state.assistant_service.send_message(
                context=context,
                conversation_id=conversation_id,
                content=payload.content,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="conversation_not_found") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _message_response(message)

    @app.get(
        "/v1/conversations/{conversation_id}/messages",
        response_model=list[MessageResponse],
    )
    def history(
        conversation_id: str,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.CONVERSATION_READ)),
    ) -> list[MessageResponse]:
        try:
            messages = request.app.state.assistant_service.history(
                context=context,
                conversation_id=conversation_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="conversation_not_found") from exc
        return [_message_response(message) for message in messages]

    @app.post(
        "/v1/conversations/{conversation_id}/handoff",
        response_model=ConversationResponse,
    )
    def handoff(
        conversation_id: str,
        payload: HandoffRequest,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.CONVERSATION_HANDOFF)),
    ) -> ConversationResponse:
        try:
            conversation = request.app.state.assistant_service.handoff(
                context=context,
                conversation_id=conversation_id,
                reason=payload.reason,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="conversation_not_found") from exc
        return _conversation_response(conversation)



    @app.get("/v1/integrations/catalog", response_model=list[IntegrationProviderResponse])
    def integration_catalog(
        request: Request,
        _context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_READ)
        ),
    ) -> list[IntegrationProviderResponse]:
        return [
            IntegrationProviderResponse(
                provider_key=item.provider_key,
                integration_type=item.integration_type,
                display_name=item.display_name,
                definition_version=item.definition_version,
                config_fields=list(item.config_fields),
                required_config_fields=list(item.required_config_fields),
                secret_fields=list(item.secret_fields),
                capabilities=list(item.capabilities),
            )
            for item in request.app.state.integration_service.catalog()
        ]

    @app.get("/v1/integrations", response_model=list[IntegrationResponse])
    def list_integrations(
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_READ)
        ),
    ) -> list[IntegrationResponse]:
        return [
            _integration_response(item)
            for item in request.app.state.integration_service.list(context)
        ]

    @app.post("/v1/integrations", response_model=IntegrationResponse)
    def connect_integration(
        payload: IntegrationConnectRequest,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        try:
            connection = request.app.state.integration_service.connect(
                context,
                provider_key=payload.provider_key,
                config=payload.config,
                secrets={
                    name: value.get_secret_value()
                    for name, value in payload.secrets.items()
                },
                source=payload.source,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _integration_response(connection)

    @app.put(
        "/v1/integrations/{connection_id}/config",
        response_model=IntegrationResponse,
    )
    def update_integration_config(
        connection_id: str,
        payload: IntegrationConfigRequest,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        try:
            connection = request.app.state.integration_service.update_config(
                context,
                connection_id,
                config=payload.config,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _integration_response(connection)

    @app.post(
        "/v1/integrations/{connection_id}/rotate",
        response_model=IntegrationResponse,
    )
    def rotate_integration_credentials(
        connection_id: str,
        payload: IntegrationRotateRequest,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        try:
            connection = request.app.state.integration_service.rotate(
                context,
                connection_id,
                secrets={
                    name: value.get_secret_value()
                    for name, value in payload.secrets.items()
                },
                source=payload.source,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _integration_response(connection)

    @app.post(
        "/v1/integrations/{connection_id}/validate",
        response_model=IntegrationValidationResponse,
    )
    def validate_integration(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationValidationResponse:
        try:
            result = request.app.state.integration_service.validate(
                context,
                connection_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return IntegrationValidationResponse(
            validation_id=result.validation_id,
            connection_id=result.connection_id,
            revision=result.revision,
            success=result.success,
            code=result.code,
        )

    @app.post(
        "/v1/integrations/{connection_id}/activate",
        response_model=IntegrationResponse,
    )
    def activate_integration(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        try:
            connection = request.app.state.integration_service.activate(
                context,
                connection_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _integration_response(connection)

    @app.post(
        "/v1/integrations/{connection_id}/disable",
        response_model=IntegrationResponse,
    )
    def disable_integration(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        try:
            connection = request.app.state.integration_service.disable(
                context,
                connection_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _integration_response(connection)

    @app.post(
        "/v1/integrations/{connection_id}/revoke",
        response_model=IntegrationResponse,
    )
    def revoke_integration(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        try:
            connection = request.app.state.integration_service.revoke(
                context,
                connection_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _integration_response(connection)

    @app.get(
        "/v1/integrations/{connection_id}/secrets",
        response_model=list[IntegrationSecretMetadataResponse],
    )
    def integration_secret_metadata(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_READ)
        ),
    ) -> list[IntegrationSecretMetadataResponse]:
        try:
            rows = request.app.state.integration_repository.secret_metadata(
                context,
                connection_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [
            IntegrationSecretMetadataResponse(
                secret_name=row.secret_name,
                version=row.version,
                source=row.source.value,
                storage_backend=row.storage_backend.value,
                active=row.active,
                expires_at=row.expires_at.isoformat() if row.expires_at else None,
                revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
            )
            for row in rows
        ]


    @app.post(
        "/internal/v1/command/assistant-plans/commercial-status",
        include_in_schema=False,
    )
    async def internal_command_commercial_status(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 1024:
            raise HTTPException(status_code=401, detail="license.commercial_denied")
        try:
            payload = CommandCommercialStatusPayload.model_validate_json(raw)
            data = commercial_license_transition.read_status(
                raw_body=raw,
                headers={
                    "key_id":request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp":request.headers.get("X-FM-Command-Timestamp"),
                    "nonce":request.headers.get("X-FM-Command-Nonce"),
                    "signature":request.headers.get("X-FM-Command-Signature"),
                },
                **payload.model_dump(),
            )
        except (CommercialLicenseTransitionDenied, ValidationError) as exc:
            raise HTTPException(
                status_code=401,detail="license.commercial_denied",
            ) from exc
        return JSONResponse(data,headers={"Cache-Control":"no-store"})

    @app.post(
        "/internal/v1/command/assistant-plans/commercial-transition",
        include_in_schema=False,
    )
    async def internal_command_commercial_transition(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 3072:
            raise HTTPException(status_code=401, detail="license.commercial_denied")
        try:
            payload = CommandCommercialTransitionPayload.model_validate_json(raw)
            status = commercial_license_transition.apply(
                raw_body=raw,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                **payload.model_dump(),
            )
        except (CommercialLicenseTransitionDenied, ValidationError) as exc:
            raise HTTPException(
                status_code=401, detail="license.commercial_denied",
            ) from exc
        return JSONResponse(
            {"status": status}, headers={"Cache-Control": "no-store"},
        )

    @app.post(
        "/internal/v1/command/assistant-plans/security-hold",
        include_in_schema=False,
    )
    async def internal_command_license_security_hold(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 2048:
            raise HTTPException(status_code=401, detail="license.security_hold_denied")
        try:
            payload = CommandLicenseSecurityHoldPayload.model_validate_json(raw)
            outcome = license_security_hold.suspend(
                raw_body=raw,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                **payload.model_dump(),
            )
        except (LicenseSecurityHoldDenied, ValidationError) as exc:
            raise HTTPException(
                status_code=401, detail="license.security_hold_denied",
            ) from exc
        return JSONResponse(
            {"status": outcome}, headers={"Cache-Control": "no-store"},
        )

    @app.post("/internal/v1/command/assistant-plans/bind", include_in_schema=False)
    async def internal_command_plan_bind(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 4096:
            raise HTTPException(status_code=401, detail="plan_binding_denied")
        try:
            payload = PlanLicenseBindPayload.model_validate_json(raw)
            state = plan_license_binding.bind(
                raw_body=raw,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                **payload.model_dump(),
            )
        except (PlanLicenseBindingDenied, ValidationError) as exc:
            raise HTTPException(status_code=401, detail="plan_binding_denied") from exc
        return JSONResponse(
            {"status": state}, headers={"Cache-Control": "no-store"},
        )

    @app.post(
        "/internal/v1/command/assistant-plans/binding-status",
        include_in_schema=False,
    )
    async def internal_command_plan_binding_status(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 2048:
            raise HTTPException(status_code=401, detail="plan_binding_denied")
        try:
            payload = PlanBindingStatusPayload.model_validate_json(raw)
            status = plan_license_binding.binding_status(
                raw_body=raw,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                **payload.model_dump(),
            )
        except (PlanLicenseBindingDenied, ValidationError) as exc:
            raise HTTPException(status_code=401, detail="plan_binding_denied") from exc
        return JSONResponse(
            {"status": status}, headers={"Cache-Control": "no-store"},
        )

    @app.post("/internal/v1/command/whatsapp-qr/policy", include_in_schema=False)
    async def internal_command_whatsapp_qr_policy(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 2048:
            raise HTTPException(status_code=401, detail="qr_policy_denied")
        try:
            payload = CommandQrDisplayPolicyPayload.model_validate_json(raw)
            result = qr_display_policy.apply(
                raw_body=raw,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                **payload.model_dump(),
            )
        except (QrDisplayPolicyDenied, ValidationError) as exc:
            raise HTTPException(status_code=401, detail="qr_policy_denied") from exc
        return JSONResponse({"status": result}, headers={"Cache-Control": "no-store"})

    @app.post("/internal/v1/command/assistant-plans/project", include_in_schema=False)
    async def internal_command_plan_projection(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 12000:
            raise HTTPException(status_code=401, detail="plan_sync_denied")
        try:
            payload = CommandPlanProjectionPayload.model_validate_json(raw)
            result = plan_projection.apply(
                raw_body=raw,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                product_code=payload.product_code,
                organization_id=payload.organization_id,
                actor_user_id=payload.actor_user_id,
                approved_at=payload.approved_at,
                plan_code=payload.plan_code,
                revision=payload.revision,
                label=payload.label,
                allowances=tuple(item.model_dump() for item in payload.allowances),
            )
        except (PlanSyncDenied, ValidationError) as exc:
            raise HTTPException(status_code=401, detail="plan_sync_denied") from exc
        return JSONResponse(
            {"status": result}, headers={"Cache-Control": "no-store"}
        )

    @app.post("/internal/v1/assistant/core-plan-grant", include_in_schema=False)
    async def internal_assistant_core_plan_grant(request: Request) -> Response:
        """No browser auth: dedicated service signature and live license lookup."""
        raw = await request.body()
        try:
            signed, signature = authenticated_core_plan_grant(
                raw_body=raw,
                request_signature=request.headers.get("X-FM-Core-Plan-Signature"),
                secret=cfg.core_plan_signing_key,
                sessions=session_factory,
                now=datetime.now(UTC),
            )
        except PlanLimitDenied as exc:
            raise HTTPException(
                status_code=401, detail="plan_grant_denied"
            ) from exc
        return Response(
            content=signed, media_type="application/json",
            headers={
                "X-FM-Assistant-Plan-Signature": signature,
                "Cache-Control": "no-store",
            },
        )

    @app.post("/internal/v1/command/core-bridge/manage", include_in_schema=False)
    async def internal_command_core_bridge_manage(request: Request) -> JSONResponse:
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=401, detail="command_bridge_denied")
        try:
            payload = CommandBridgeManagePayload.model_validate_json(body)
            result = command_bridge.execute(
                raw_body=body,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                action=payload.action,
                tenant_id=payload.tenant_id,
                unit_id=payload.unit_id,
                capability=payload.capability,
                target_key_id=payload.target_key_id,
                actor_user_id=payload.actor_user_id,
                organization_id=payload.organization_id,
                step_up_at=payload.step_up_at,
                command_request_id=payload.command_request_id,
            )
        except (CommandBridgeDenied, ValidationError) as exc:
            raise HTTPException(status_code=401, detail="command_bridge_denied") from exc
        return JSONResponse(
            {"status": result},
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/internal/v1/command/core-bridge/status", include_in_schema=False)
    async def internal_command_core_bridge_status(request: Request) -> JSONResponse:
        """Signed, scope-restricted mutation lookup. Never performs a mutation."""
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=401, detail="command_bridge_denied")
        try:
            payload = CommandBridgeManagePayload.model_validate_json(body)
            result = command_bridge.reconcile_status(
                raw_body=body,
                headers={
                    "key_id": request.headers.get("X-FM-Command-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Command-Timestamp"),
                    "nonce": request.headers.get("X-FM-Command-Nonce"),
                    "signature": request.headers.get("X-FM-Command-Signature"),
                },
                action=payload.action,
                tenant_id=payload.tenant_id,
                unit_id=payload.unit_id,
                capability=payload.capability,
                target_key_id=payload.target_key_id,
                actor_user_id=payload.actor_user_id,
                organization_id=payload.organization_id,
                step_up_at=payload.step_up_at,
                command_request_id=payload.command_request_id,
            )
        except (CommandBridgeDenied, ValidationError) as exc:
            raise HTTPException(status_code=401, detail="command_bridge_denied") from exc
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.post("/internal/v1/core/credentials/resolve", include_in_schema=False)
    async def internal_core_credential_resolve(request: Request) -> JSONResponse:
        # Internal-only ingress with network ACL/TLS; never trust browser auth.
        raw = await request.body()
        if len(raw) > 4096:
            raise HTTPException(status_code=401, detail="core_bridge_denied")
        try:
            payload = CoreBridgeResolvePayload.model_validate_json(raw)
            secret = core_bridge.resolve(
                headers={
                    "key_id": request.headers.get("X-FM-Core-Key-ID"),
                    "timestamp": request.headers.get("X-FM-Core-Timestamp"),
                    "nonce": request.headers.get("X-FM-Core-Nonce"),
                    "signature": request.headers.get("X-FM-Core-Signature"),
                },
                raw_body=raw,
                tenant_id=payload.tenant_id,
                unit_id=payload.unit_id,
                capability=payload.capability,
                connection_id=payload.connection_id,
            )
        except (CoreBridgeDenied, ValidationError) as exc:
            raise HTTPException(status_code=401, detail="core_bridge_denied") from exc
        return JSONResponse(
            {"secret": secret}, headers={"Cache-Control": "no-store"}
        )

    @app.post("/v1/channels/whatsapp/qr/provision", response_model=IntegrationResponse)
    def provision_whatsapp_qr(
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        onboarding = request.app.state.evolution_onboarding
        if onboarding is None:
            raise HTTPException(status_code=503, detail="evolution_gateway_unavailable")
        try:
            connection = onboarding.provision(context)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        audit.record(
            context=context,
            action="assistant.channel.whatsapp.qr.provision",
            resource_type="integration",
            resource_id=connection.connection_id,
            outcome="success",
        )
        return _integration_response(connection)

    @app.post(
        "/v1/channels/whatsapp/qr/{connection_id}/pause",
        response_model=IntegrationResponse,
    )
    def pause_whatsapp_qr(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        onboarding = request.app.state.evolution_onboarding
        if onboarding is None:
            raise HTTPException(status_code=503, detail="evolution_gateway_unavailable")
        try:
            connection = onboarding.pause(context, connection_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="evolution_connection_not_found") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        audit.record(
            context=context,
            action="assistant.channel.whatsapp.qr.paused_local",
            resource_type="integration",
            resource_id=connection.connection_id,
            outcome="success",
        )
        return _integration_response(connection)

    @app.post(
        "/v1/channels/whatsapp/qr/{connection_id}/resume",
        response_model=IntegrationResponse,
    )
    def resume_whatsapp_qr(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        onboarding = request.app.state.evolution_onboarding
        if onboarding is None:
            raise HTTPException(status_code=503, detail="evolution_gateway_unavailable")
        try:
            connection = onboarding.resume(context, connection_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="evolution_connection_not_found") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        audit.record(
            context=context,
            action="assistant.channel.whatsapp.qr.resume_verified",
            resource_type="integration",
            resource_id=connection.connection_id,
            outcome="success",
        )
        return _integration_response(connection)

    @app.post(
        "/v1/channels/whatsapp/qr/{connection_id}/logout",
        response_model=IntegrationResponse,
    )
    def logout_whatsapp_qr(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> IntegrationResponse:
        onboarding = request.app.state.evolution_onboarding
        if onboarding is None:
            raise HTTPException(status_code=503, detail="evolution_gateway_unavailable")
        try:
            connection = onboarding.logout(context, connection_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="evolution_connection_not_found") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        audit.record(
            context=context,
            action="assistant.channel.whatsapp.qr.logout_confirmed",
            resource_type="integration",
            resource_id=connection.connection_id,
            outcome="success",
        )
        return _integration_response(connection)

    @app.get("/v1/channels/whatsapp/qr/panel", response_class=HTMLResponse)
    def whatsapp_qr_panel(
        _principal: SessionPrincipal = Depends(
            human_permission(Permission.INTEGRATION_READ)
        ),
    ) -> HTMLResponse:
        markup, csp = render_qr_page()
        return HTMLResponse(
            markup, headers={
                "Content-Security-Policy": csp,
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            },
        )

    @app.get("/v1/channels/whatsapp/qr/current")
    def current_whatsapp_qr(
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_READ)
        ),
    ) -> Response:
        onboarding = request.app.state.evolution_onboarding
        if onboarding is None:
            raise HTTPException(status_code=503, detail="evolution_gateway_unavailable")
        connection = onboarding.current(context)
        try:
            display_seconds, policy_revision = qr_display_policy.read()
        except Exception as exc:
            # Missing policy read-model is not an authorization to show stale
            # or excessive QR codes. Remain unavailable rather than widen cap.
            raise HTTPException(status_code=503, detail="qr_policy_unavailable") from exc
        return JSONResponse(
            {"connection_id": connection.connection_id if connection else None,
             "status": connection.status.value if connection else "disconnected",
             "qr_display_seconds": display_seconds,
             "qr_policy_revision": policy_revision},
            headers={"Cache-Control": "no-store"},
        )

    @app.get(
        "/v1/channels/whatsapp/qr/{connection_id}",
        response_model=QRConnectionResponse,
    )
    def get_whatsapp_qr(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_READ)
        ),
    ) -> Response:
        onboarding = request.app.state.evolution_onboarding
        if onboarding is None:
            raise HTTPException(status_code=503, detail="evolution_gateway_unavailable")
        try:
            snapshot = onboarding.qr(context, connection_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse(
            QRConnectionResponse(
                connection_id=snapshot.connection_id,
                status=snapshot.status, qr_data_url=snapshot.qr_data_url,
            ).model_dump(),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @app.get("/v1/channels/whatsapp/qr/{connection_id}/operations")
    def whatsapp_queue_operations(
        connection_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_READ)
        ),
    ) -> Response:
        connection = integration_repository.get(context, connection_id)
        if connection is None or connection.provider_key != "whatsapp_evolution":
            raise HTTPException(status_code=404, detail="evolution_connection_not_found")
        queue = EvolutionInboundQueue(
            session_factory, vault,
            max_pending_per_connection=cfg.evolution_max_pending_per_connection,
        )
        return JSONResponse(
            queue.operational_snapshot(connection_id=connection_id),
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/v1/channels/whatsapp/qr/{connection_id}/operations/{message_id}/review")
    def whatsapp_queue_review(
        connection_id: str,
        message_id: str,
        request: Request,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> Response:
        connection = integration_repository.get(context, connection_id)
        if connection is None or connection.provider_key != "whatsapp_evolution":
            raise HTTPException(status_code=404, detail="evolution_connection_not_found")
        queue = EvolutionInboundQueue(session_factory, vault)
        if not queue.acknowledge_reconciliation(
            connection_id=connection_id, message_id=message_id,
        ):
            raise HTTPException(status_code=409, detail="evolution_reconciliation_not_pending")
        audit.record(
            context=context, action="assistant.channel.whatsapp.reconciliation_reviewed",
            resource_type="integration", resource_id=connection_id, outcome="success",
        )
        return JSONResponse({"status": "reviewed"}, headers={"Cache-Control": "no-store"})

    @app.post(
        "/v1/channels/whatsapp/qr/{connection_id}/operations/{message_id}/investigate"
    )
    def whatsapp_investigate_uncertain(
        connection_id: str,
        message_id: str,
        payload: EvolutionEvidenceInvestigationRequest,
        context: TenantContext = Depends(
            tenant_with_permission(Permission.INTEGRATION_MANAGE)
        ),
    ) -> Response:
        """Read-only provider evidence candidate. Never clears quarantine."""
        connection = integration_repository.get(context, connection_id)
        if connection is None or connection.provider_key != "whatsapp_evolution":
            raise HTTPException(status_code=404, detail="evolution_connection_not_found")
        queue = EvolutionInboundQueue(session_factory, vault)
        if not queue.can_investigate_missing_reference(
            connection_id=connection_id, message_id=message_id,
            operation_id=payload.operation_id,
        ):
            raise HTTPException(status_code=409, detail="evolution_evidence_not_pending")
        onboarding = evolution_onboarding
        if onboarding is None:
            raise HTTPException(status_code=503, detail="evolution_evidence_provider_unavailable")
        secret = integration_repository.active_secret_ciphertexts(connection_id).get(
            "instance_token"
        )
        if secret is None:
            raise HTTPException(status_code=409, detail="evolution_evidence_provider_unavailable")
        try:
            digest = onboarding._transport.find_outbound_evidence(
                str(connection.config["instance_name"]),
                instance_token=vault.decrypt(secret),
                provider_reference=payload.provider_reference,
            )
        except EvolutionUnavailable as exc:
            raise HTTPException(
                status_code=503, detail="evolution_evidence_provider_unavailable",
            ) from exc
        if digest is None:
            raise HTTPException(status_code=404, detail="evolution_evidence_not_found")
        if not queue.stage_provider_evidence_candidate(
            connection_id=connection_id, message_id=message_id,
            operation_id=payload.operation_id,
            provider_reference=payload.provider_reference, evidence_digest=digest,
        ):
            raise HTTPException(status_code=409, detail="evolution_evidence_conflict")
        audit.record(
            context=context, action="assistant.channel.whatsapp.evidence_candidate_staged",
            resource_type="integration", resource_id=connection_id, outcome="success",
        )
        return JSONResponse(
            {"status": "candidate_only", "reconciled": False, "automatic_resend": False},
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/webhooks/evolution-native/{connection_id}", status_code=204)
    async def receive_native_evolution(
        connection_id: str, request: Request,
        x_fm_evolution_token: str | None = Header(default=None),
    ) -> Response:
        ingress = request.app.state.evolution_native_ingress
        if ingress is None:
            raise HTTPException(status_code=503, detail="evolution_native_unavailable")
        if request.headers.get("content-length", "").isdigit() and (
            int(request.headers["content-length"]) > 65536
        ):
            raise HTTPException(status_code=413, detail="evolution_webhook_too_large")
        raw = await request.body()
        if len(raw) > 65536:
            raise HTTPException(status_code=413, detail="evolution_webhook_too_large")
        try:
            ingress.receive(
                connection_id=connection_id, raw=raw,
                token=x_fm_evolution_token,
            )
        except EvolutionQueueCapacityExceeded as exc:
            raise HTTPException(status_code=429, detail="evolution_queue_full", headers={"Retry-After": "5"}) from exc
        except (NativeEvolutionDenied, EvolutionEventDenied, PermissionError, LookupError) as exc:
            raise HTTPException(status_code=401, detail="evolution_native_denied") from exc
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @app.post("/webhooks/fm-evolution/{connection_id}", status_code=204)
    async def receive_fm_evolution(
        connection_id: str, request: Request,
        x_fm_evolution_signature: str | None = Header(default=None),
        x_fm_evolution_timestamp: str | None = Header(default=None),
    ) -> Response:
        runtime = request.app.state.evolution_runtime
        if runtime is None:
            raise HTTPException(status_code=503, detail="evolution_webhook_unavailable")
        if request.headers.get("content-length", "").isdigit() and (
            int(request.headers["content-length"]) > 65536
        ):
            raise HTTPException(status_code=413, detail="evolution_webhook_too_large")
        raw = await request.body()
        if len(raw) > 65536:
            raise HTTPException(status_code=413, detail="evolution_webhook_too_large")
        try:
            runtime.receive(
                connection_id=connection_id, raw=raw,
                signature=x_fm_evolution_signature,
                timestamp=x_fm_evolution_timestamp,
            )
        except EvolutionQueueCapacityExceeded as exc:
            raise HTTPException(status_code=429, detail="evolution_queue_full", headers={"Retry-After": "5"}) from exc
        except (EvolutionEventDenied, PermissionError, LookupError) as exc:
            raise HTTPException(status_code=401, detail="evolution_webhook_denied") from exc
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @app.put("/v1/channels/whatsapp", response_model=WhatsAppChannelResponse)
    def configure_whatsapp(
        payload: WhatsAppChannelRequest,
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.INTEGRATION_MANAGE)),
    ) -> WhatsAppChannelResponse:
        config = request.app.state.whatsapp_channels.configure(
            context,
            phone_number_id=payload.phone_number_id,
            business_account_id=payload.business_account_id,
            access_token=payload.access_token.get_secret_value(),
            app_secret=payload.app_secret.get_secret_value(),
            verify_token=payload.verify_token.get_secret_value(),
            graph_api_version=payload.graph_api_version,
        )
        audit.record(
            context=context,
            action="assistant.channel.whatsapp.configure",
            resource_type="whatsapp_channel",
            resource_id=config.channel_id,
            outcome="success",
        )
        return WhatsAppChannelResponse(
            channel_id=config.channel_id,
            phone_number_id=config.phone_number_id,
            business_account_id=config.business_account_id,
            graph_api_version=config.graph_api_version,
            webhook_path=f"/webhooks/meta/whatsapp/{config.channel_id}",
        )

    @app.get("/v1/channels/whatsapp", response_model=WhatsAppChannelResponse)
    def get_whatsapp(
        request: Request,
        context: TenantContext = Depends(tenant_with_permission(Permission.INTEGRATION_READ)),
    ) -> WhatsAppChannelResponse:
        config = request.app.state.whatsapp_channels.get_for_context(context)
        if config is None:
            raise HTTPException(status_code=404, detail="whatsapp_channel_not_found")
        return WhatsAppChannelResponse(
            channel_id=config.channel_id,
            phone_number_id=config.phone_number_id,
            business_account_id=config.business_account_id,
            graph_api_version=config.graph_api_version,
            webhook_path=f"/webhooks/meta/whatsapp/{config.channel_id}",
        )

    @app.get("/webhooks/meta/whatsapp/{channel_id}")
    def verify_whatsapp_webhook(
        channel_id: str,
        hub_mode: str = Query(alias="hub.mode"),
        hub_verify_token: str = Query(alias="hub.verify_token"),
        hub_challenge: str = Query(alias="hub.challenge"),
    ) -> Response:
        if hub_mode != "subscribe":
            raise HTTPException(status_code=400, detail="meta_mode_invalid")
        try:
            challenge = whatsapp_runtime.verify_challenge(
                channel_id=channel_id,
                verify_token=hub_verify_token,
                challenge=hub_challenge,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="whatsapp_channel_not_found") from exc
        except WhatsAppProviderError as exc:
            raise HTTPException(status_code=401, detail="meta_verification_failed") from exc
        return Response(content=challenge, media_type="text/plain")

    @app.post("/webhooks/meta/whatsapp/{channel_id}", status_code=204)
    async def receive_whatsapp_webhook(
        channel_id: str,
        request: Request,
        x_hub_signature_256: str | None = Header(
            default=None,
            alias="X-Hub-Signature-256",
        ),
    ) -> Response:
        if not x_hub_signature_256:
            raise HTTPException(status_code=401, detail="meta_signature_missing")
        body = await request.body()
        try:
            result = whatsapp_runtime.process_webhook(
                channel_id=channel_id,
                body=body,
                signature=x_hub_signature_256,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="whatsapp_channel_not_found") from exc
        except WhatsAppProviderError as exc:
            raise HTTPException(status_code=401, detail="meta_signature_invalid") from exc
        if result.failed:
            raise HTTPException(status_code=503, detail="whatsapp_processing_failed")
        return Response(status_code=204)

    return app
