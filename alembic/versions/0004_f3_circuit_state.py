"""F3.8 additive persistent provider circuit states.

Revision ID: f3_0004
Revises: f3_0003
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3_0004"
down_revision = "f3_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_ai_provider_circuit_state",
        sa.Column(
            "provider_id", sa.String(128),
            sa.ForeignKey("core_ai_providers.provider_id"), primary_key=True,
        ),
        sa.Column("phase", sa.String(12), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("probe_id", sa.String(128), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("version >= 0", name="ck_ai_circuit_version"),
        sa.CheckConstraint("failures >= 0", name="ck_ai_circuit_failures"),
        sa.CheckConstraint(
            "phase in ('closed','open','half_open')", name="ck_ai_circuit_phase",
        ),
    )


def downgrade() -> None:
    # Destructive downgrade permitted only in disposable CI databases.
    op.drop_table("core_ai_provider_circuit_state")
