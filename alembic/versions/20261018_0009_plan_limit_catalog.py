"""Add plan revisions and scoped resource ceilings, with no automatic rollout.

Revision ID: 20261018_0009
Revises: 20261018_0008
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261018_0009"
down_revision = "20261018_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_tenant_licenses",
        sa.Column("plan_revision", sa.Integer(), nullable=True),
    )
    op.create_table(
        "assistant_plan_versions",
        sa.Column("plan_code", sa.String(120), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_plan_revision_positive"),
        sa.CheckConstraint(
            "status in ('draft','published','retired')",
            name="ck_plan_version_status",
        ),
    )
    op.create_table(
        "assistant_plan_limits",
        sa.Column("plan_code", sa.String(120), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("resource", sa.String(80), primary_key=True),
        sa.Column("scope", sa.String(12), nullable=False),
        sa.Column("limit_units", sa.BigInteger(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_code", "revision"],
            ["assistant_plan_versions.plan_code", "assistant_plan_versions.revision"],
        ),
        sa.CheckConstraint("limit_units > 0", name="ck_plan_limit_positive"),
        sa.CheckConstraint("window_seconds > 0", name="ck_plan_window_positive"),
        sa.CheckConstraint("scope in ('tenant','unit')", name="ck_plan_scope"),
    )


def downgrade() -> None:
    # Destructive downgrade for disposable databases ONLY.
    op.drop_table("assistant_plan_limits")
    op.drop_table("assistant_plan_versions")
    op.drop_column("assistant_tenant_licenses", "plan_revision")
