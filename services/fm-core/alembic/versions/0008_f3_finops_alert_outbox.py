"""F3: durable FM FinOps operational alert outbox, no external dispatch.

Revision ID: f3_0008
Revises: f3_0007
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3_0008"
down_revision = "f3_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_ai_finops_alert_outbox",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("reasons_json", sa.String(500), nullable=False),
        sa.Column("known_cost_subtotal", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("unknown_attempts", sa.Integer(), nullable=False),
        sa.Column("observed_attempts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_core_finops_alert_outbox_scope", "core_ai_finops_alert_outbox",
        ["tenant_id", "unit_id", "status", "created_at"],
    )


def downgrade() -> None:
    # Disposable internal CI database only. Never downgrade production data.
    op.drop_index(
        "ix_core_finops_alert_outbox_scope",
        table_name="core_ai_finops_alert_outbox",
    )
    op.drop_table("core_ai_finops_alert_outbox")
