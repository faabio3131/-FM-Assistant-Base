"""F3.8 additive deterministic quota policy and reservation ledger.

Revision ID: f3_0003
Revises: f3_0002
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3_0003"
down_revision = "f3_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_ai_quota_policies",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("unit_id", sa.String(128), primary_key=True),
        sa.Column("capability", sa.String(80), primary_key=True),
        sa.Column("limit_units", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("limit_units > 0", name="ck_ai_quota_positive_limit"),
        sa.CheckConstraint("window_seconds > 0", name="ck_ai_quota_positive_window"),
    )
    op.create_table(
        "core_ai_quota_reservations",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("unit_id", sa.String(128), primary_key=True),
        sa.Column("capability", sa.String(80), primary_key=True),
        sa.Column("request_id", sa.String(128), primary_key=True),
        sa.Column("period", sa.BigInteger(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("reserved_units", sa.Integer(), nullable=False),
        sa.Column("consumed_units", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id", "capability"],
            ["core_ai_quota_policies.tenant_id", "core_ai_quota_policies.unit_id",
             "core_ai_quota_policies.capability"],
        ),
        sa.CheckConstraint("reserved_units > 0", name="ck_ai_quota_reserved_positive"),
        sa.CheckConstraint("consumed_units >= 0", name="ck_ai_quota_consumed_nonnegative"),
    )
    op.create_index(
        "ix_core_ai_quota_reservations_period", "core_ai_quota_reservations", ["period"],
    )


def downgrade() -> None:
    # Only permitted on disposable databases, never automatically on production.
    op.drop_index("ix_core_ai_quota_reservations_period",
                  table_name="core_ai_quota_reservations")
    op.drop_table("core_ai_quota_reservations")
    op.drop_table("core_ai_quota_policies")
