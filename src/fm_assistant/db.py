"""Persistência SQLAlchemy do SaaS, sem dependência do Kordena."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class TenantCredentialORM(Base):
    __tablename__ = "assistant_tenant_credentials"

    credential_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_assistant_credential_scope", "tenant_id", "unit_id", "active"),
    )


class PersonaORM(Base):
    __tablename__ = "assistant_personas"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    public_name: Mapped[str] = mapped_column(String(160), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="pt-BR")
    tone: Mapped[str] = mapped_column(String(120), nullable=False, default="profissional")
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversationORM(Base):
    __tablename__ = "assistant_conversations"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_assistant_conversation_scope", "tenant_id", "unit_id", "updated_at"),
        Index("ix_assistant_conversation_external", "tenant_id", "unit_id", "external_ref"),
    )


class MessageORM(Base):
    __tablename__ = "assistant_messages"

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_assistant_message_scope",
            "tenant_id",
            "unit_id",
            "conversation_id",
            "created_at",
        ),
    )


class KnowledgeDocumentORM(Base):
    __tablename__ = "assistant_knowledge_documents"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_assistant_knowledge_scope", "tenant_id", "unit_id", "active"),
    )


class AuditEventORM(Base):
    __tablename__ = "assistant_audit_events"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)



class WhatsAppChannelORM(Base):
    __tablename__ = "assistant_whatsapp_channels"

    channel_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    phone_number_id: Mapped[str] = mapped_column(String(128), nullable=False)
    business_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    access_token_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    app_secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    verify_token_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    graph_api_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v23.0")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_assistant_whatsapp_scope",
            "tenant_id",
            "unit_id",
            "enabled",
        ),
    )


class WhatsAppInboundORM(Base):
    __tablename__ = "assistant_whatsapp_inbound"

    channel_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_whatsapp_channels.channel_id", ondelete="CASCADE"),
        primary_key=True,
    )
    message_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    sender_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    outbound_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_assistant_whatsapp_inbound_status",
            "channel_id",
            "status",
            "updated_at",
        ),
    )


class TenantORM(Base):
    __tablename__ = "assistant_tenants"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UnitORM(Base):
    __tablename__ = "assistant_units"

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserORM(Base):
    __tablename__ = "assistant_users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MembershipORM(Base):
    __tablename__ = "assistant_memberships"

    membership_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_assistant_membership_tenant_user"),
    )


class MembershipUnitORM(Base):
    __tablename__ = "assistant_membership_units"

    membership_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_memberships.membership_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
    )


class SessionORM(Base):
    __tablename__ = "assistant_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    membership_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_memberships.membership_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    active_unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "active_unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
    )


class InvitationORM(Base):
    __tablename__ = "assistant_invitations"

    invitation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
    )


class PasswordResetORM(Base):
    __tablename__ = "assistant_password_resets"

    reset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TenantLicenseORM(Base):
    __tablename__ = "assistant_tenant_licenses"

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    plan_code: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EntitlementORM(Base):
    __tablename__ = "assistant_entitlements"

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    capability: Mapped[str] = mapped_column(String(160), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="plan")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IntegrationProviderORM(Base):
    __tablename__ = "assistant_integration_providers"

    provider_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    integration_type: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IntegrationConnectionORM(Base):
    __tablename__ = "assistant_integration_connections"

    connection_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_key: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("assistant_integration_providers.provider_key"),
        nullable=False,
        index=True,
    )
    integration_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
        Index(
            "ix_assistant_integration_scope",
            "tenant_id",
            "unit_id",
            "provider_key",
            "status",
        ),
    )


class IntegrationSecretVersionORM(Base):
    __tablename__ = "assistant_integration_secret_versions"

    connection_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
        primary_key=True,
    )
    secret_name: Mapped[str] = mapped_column(String(120), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(64), nullable=False)
    ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_assistant_integration_secret_active",
            "connection_id",
            "secret_name",
            "active",
        ),
    )


class IntegrationCapabilityORM(Base):
    __tablename__ = "assistant_integration_capabilities"

    connection_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
        primary_key=True,
    )
    capability: Mapped[str] = mapped_column(String(160), primary_key=True)


class IntegrationInboundORM(Base):
    __tablename__ = "assistant_integration_inbound"

    channel_id: Mapped[str] = mapped_column(
        "connection_id",
        String(64),
        ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
        primary_key=True,
    )
    message_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    sender_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    outbound_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_assistant_integration_inbound_status",
            "connection_id",
            "status",
            "updated_at",
        ),
    )


class IntegrationValidationORM(Base):
    __tablename__ = "assistant_integration_validations"

    validation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_assistant_integration_validation_latest",
            "connection_id",
            "created_at",
        ),
    )


class IntegrationEventORM(Base):
    __tablename__ = "assistant_integration_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_assistant_integration_event_scope",
            "tenant_id",
            "unit_id",
            "created_at",
        ),
    )


def create_session_factory(database_url: str):
    kwargs = {}
    if database_url.lower().startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, pool_pre_ping=True, **kwargs)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)


class PlanVersionORM(Base):
    """Immutable catalog revision; never stores price or provider secrets."""

    __tablename__ = "assistant_plan_versions"

    plan_code: Mapped[str] = mapped_column(String(120), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlanLimitORM(Base):
    """Per-plan metric ceiling; no implicit unlimited fallback."""

    __tablename__ = "assistant_plan_limits"

    plan_code: Mapped[str] = mapped_column(String(120), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource: Mapped[str] = mapped_column(String(80), primary_key=True)
    scope: Mapped[str] = mapped_column(String(12), nullable=False)
    limit_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_code", "revision"],
            ["assistant_plan_versions.plan_code", "assistant_plan_versions.revision"],
        ),
    )
