"""Add universal WhatsApp channel.

Revision ID: 20261003_0002
Revises: 20261003_0001
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20261003_0002"
down_revision = "20261003_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_whatsapp_channels",
        sa.Column("channel_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("phone_number_id", sa.String(length=128), nullable=False),
        sa.Column("business_account_id", sa.String(length=128), nullable=True),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("app_secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("verify_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("graph_api_version", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_whatsapp_scope",
        "assistant_whatsapp_channels",
        ["tenant_id", "unit_id", "enabled"],
    )
    op.create_table(
        "assistant_whatsapp_inbound",
        sa.Column(
            "channel_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_whatsapp_channels.channel_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("message_id", sa.String(length=160), primary_key=True),
        sa.Column("sender_hash", sa.String(length=64), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("outbound_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_whatsapp_inbound_status",
        "assistant_whatsapp_inbound",
        ["channel_id", "status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_whatsapp_inbound_status",
        table_name="assistant_whatsapp_inbound",
    )
    op.drop_table("assistant_whatsapp_inbound")
    op.drop_index(
        "ix_assistant_whatsapp_scope",
        table_name="assistant_whatsapp_channels",
    )
    op.drop_table("assistant_whatsapp_channels")
