"""Initial standalone FM Assistant SaaS schema.

Revision ID: 20261003_0001
Revises:
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20261003_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_tenant_credentials",
        sa.Column("credential_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_tenant_credentials_tenant_id",
        "assistant_tenant_credentials",
        ["tenant_id"],
    )
    op.create_index(
        "ix_assistant_tenant_credentials_unit_id",
        "assistant_tenant_credentials",
        ["unit_id"],
    )
    op.create_index(
        "ix_assistant_tenant_credentials_key_hash",
        "assistant_tenant_credentials",
        ["key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_assistant_credential_scope",
        "assistant_tenant_credentials",
        ["tenant_id", "unit_id", "active"],
    )

    op.create_table(
        "assistant_personas",
        sa.Column("tenant_id", sa.String(length=128), primary_key=True),
        sa.Column("unit_id", sa.String(length=128), primary_key=True),
        sa.Column("public_name", sa.String(length=160), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("tone", sa.String(length=120), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "assistant_conversations",
        sa.Column("conversation_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_conversation_scope",
        "assistant_conversations",
        ["tenant_id", "unit_id", "updated_at"],
    )
    op.create_index(
        "ix_assistant_conversation_external",
        "assistant_conversations",
        ["tenant_id", "unit_id", "external_ref"],
    )

    op.create_table(
        "assistant_messages",
        sa.Column("message_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_messages_conversation_id",
        "assistant_messages",
        ["conversation_id"],
    )
    op.create_index(
        "ix_assistant_message_scope",
        "assistant_messages",
        ["tenant_id", "unit_id", "conversation_id", "created_at"],
    )

    op.create_table(
        "assistant_knowledge_documents",
        sa.Column("document_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_knowledge_scope",
        "assistant_knowledge_documents",
        ["tenant_id", "unit_id", "active"],
    )

    op.create_table(
        "assistant_audit_events",
        sa.Column("audit_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("credential_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_audit_events_tenant_id",
        "assistant_audit_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_assistant_audit_events_unit_id",
        "assistant_audit_events",
        ["unit_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_audit_events_unit_id", table_name="assistant_audit_events")
    op.drop_index("ix_assistant_audit_events_tenant_id", table_name="assistant_audit_events")
    op.drop_table("assistant_audit_events")

    op.drop_index("ix_assistant_knowledge_scope", table_name="assistant_knowledge_documents")
    op.drop_table("assistant_knowledge_documents")

    op.drop_index("ix_assistant_message_scope", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_conversation_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")

    op.drop_index("ix_assistant_conversation_external", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversation_scope", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")

    op.drop_table("assistant_personas")

    op.drop_index("ix_assistant_credential_scope", table_name="assistant_tenant_credentials")
    op.drop_index("ix_assistant_tenant_credentials_key_hash", table_name="assistant_tenant_credentials")
    op.drop_index("ix_assistant_tenant_credentials_unit_id", table_name="assistant_tenant_credentials")
    op.drop_index("ix_assistant_tenant_credentials_tenant_id", table_name="assistant_tenant_credentials")
    op.drop_table("assistant_tenant_credentials")
