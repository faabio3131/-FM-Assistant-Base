"""Encrypted durable WhatsApp inbound job queue.

Revision ID: 20261019_0013
Revises: 20261019_0012
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261019_0013"
down_revision = "20261019_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_evolution_inbound_jobs",
        sa.Column("connection_id", sa.String(64), primary_key=True),
        sa.Column("message_id", sa.String(160), primary_key=True),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(160), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["assistant_integration_connections.connection_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "state in ('pending','processing','complete','reconcile_required')",
            name="ck_assistant_evolution_job_state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_assistant_evolution_job_attempts"),
    )
    op.create_index(
        "ix_assistant_evolution_inbound_pending",
        "assistant_evolution_inbound_jobs", ["state", "created_at"],
    )


def downgrade() -> None:
    # Destructive downgrade for disposable test DBs only.
    op.drop_index(
        "ix_assistant_evolution_inbound_pending",
        table_name="assistant_evolution_inbound_jobs",
    )
    op.drop_table("assistant_evolution_inbound_jobs")
