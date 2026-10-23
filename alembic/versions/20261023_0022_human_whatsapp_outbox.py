"""F5: encrypted verified WhatsApp recipient and one-shot human outbound intent."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261023_0022"
down_revision = "20261023_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_human_whatsapp_contacts",
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey(
            "assistant_conversations.conversation_id", ondelete="CASCADE",
        ), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("connection_id", sa.String(64), nullable=False),
        sa.Column("encrypted_recipient", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assistant_human_whatsapp_outbox",
        sa.Column("message_id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey(
            "assistant_conversations.conversation_id", ondelete="CASCADE",
        ), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("connection_id", sa.String(64), nullable=False),
        sa.Column("encrypted_recipient", sa.Text(), nullable=False),
        sa.Column("encrypted_message", sa.Text(), nullable=False),
        sa.Column("message_digest", sa.String(64), nullable=False),
        sa.Column("assigned_to", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("provider_reference", sa.String(160), nullable=True),
        sa.Column("operation_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_human_whatsapp_queue", "assistant_human_whatsapp_outbox",
                    ["state", "created_at"])
    op.create_index("ix_human_whatsapp_scope", "assistant_human_whatsapp_outbox",
                    ["tenant_id", "unit_id", "conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_human_whatsapp_scope", "assistant_human_whatsapp_outbox")
    op.drop_index("ix_human_whatsapp_queue", "assistant_human_whatsapp_outbox")
    op.drop_table("assistant_human_whatsapp_outbox")
    op.drop_table("assistant_human_whatsapp_contacts")
