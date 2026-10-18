"""API HTTP do FM Assistant Base SaaS."""

from __future__ import annotations

from contextlib import asynccontextmanager
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
from pydantic import BaseModel, Field, SecretStr

from .capabilities import KnowledgeCapabilityProvider
from .channel_secrets import ChannelSecretBox
from .channels.whatsapp_meta import WhatsAppProviderError
from .core_client import CoreAIClient, CoreAudioTranscriber
from .db import create_schema, create_session_factory
from .domain import AssistantPersona, Channel, Conversation, Message, TenantContext
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
        capabilities=KnowledgeCapabilityProvider(knowledge),
        audit=audit,
    )

    secret_box = ChannelSecretBox(cfg.channel_encryption_key)
    whatsapp_channels = WhatsAppChannelRepository(session_factory, secret_box)
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
        app.state.settings = cfg
        app.state.credentials = credentials
        app.state.identity_repository = identity_repository
        app.state.identity_service = identity_service
        app.state.knowledge = knowledge
        app.state.assistant_service = service
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
