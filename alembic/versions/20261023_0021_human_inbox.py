"""Human inbox handoff ownership and private operator activity.

Revision ID: 20261023_0021
Revises: 20261022_0020
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261023_0021"
down_revision = "20261022_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_human_inbox_state",
        sa.Column("conversation_id", sa.String(64),
                  sa.ForeignKey("assistant_conversations.conversation_id",
                                ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("assigned_to", sa.String(64), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_human_inbox_scope", "assistant_human_inbox_state",
                    ["tenant_id", "unit_id", "assigned_to"])
    op.create_table(
        "assistant_human_inbox_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64),
                  sa.ForeignKey("assistant_conversations.conversation_id",
                                ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("assigned_to", sa.String(64), nullable=True),
        sa.Column("private_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_human_inbox_event_scope", "assistant_human_inbox_events",
                    ["tenant_id", "unit_id", "conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_human_inbox_event_scope", "assistant_human_inbox_events")
    op.drop_table("assistant_human_inbox_events")
    op.drop_index("ix_human_inbox_scope", "assistant_human_inbox_state")
    op.drop_table("assistant_human_inbox_state")
