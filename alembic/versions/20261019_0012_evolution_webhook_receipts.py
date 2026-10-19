"""Durable replay receipt for authenticated FM Evolution webhook events.

Revision ID: 20261019_0012
Revises: 20261018_0011
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261019_0012"
down_revision = "20261018_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_evolution_webhook_receipts",
        sa.Column("connection_id", sa.String(64), nullable=False, primary_key=True),
        sa.Column("event_digest", sa.String(64), nullable=False, primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["assistant_integration_connections.connection_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_assistant_evolution_receipts_created",
        "assistant_evolution_webhook_receipts",
        ["received_at"],
    )


def downgrade() -> None:
    # Destructive downgrade is only allowed against disposable test databases.
    op.drop_index(
        "ix_assistant_evolution_receipts_created",
        table_name="assistant_evolution_webhook_receipts",
    )
    op.drop_table("assistant_evolution_webhook_receipts")
