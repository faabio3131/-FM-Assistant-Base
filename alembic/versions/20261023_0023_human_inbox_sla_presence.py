"""F5 scoped human inbox service levels and operator presence."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261023_0023"
down_revision = "20261023_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_human_inbox_sla_policies",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("unit_id", sa.String(128), primary_key=True),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("presence_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assistant_human_inbox_presence",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("unit_id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("assistant_human_inbox_presence")
    op.drop_table("assistant_human_inbox_sla_policies")
