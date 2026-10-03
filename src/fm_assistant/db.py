"""Persistência SQLAlchemy do SaaS, sem dependência do Kordena."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, create_engine
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


def create_session_factory(database_url: str):
    kwargs = {}
    if database_url.lower().startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, pool_pre_ping=True, **kwargs)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)
