"""Operational FM-owned provider usage export snapshots, append-only.

Revision ID: f3_0009
Revises: f3_0008
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3_0009"
down_revision = "f3_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_ai_provider_export_snapshots",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("adapter", sa.String(32), nullable=False),
        sa.Column("account_ref", sa.String(128), nullable=False),
        sa.Column("source_ref", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usage_json", sa.String(2048), nullable=False),
        sa.Column("cost_usd", sa.String(80), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "unit_id", "request_id", "attempt_id",
            name="uq_core_provider_export_physical_attempt",
        ),
        sa.UniqueConstraint(
            "provider", "account_ref", "source_ref",
            name="uq_core_provider_export_source_provenance",
        ),
    )
    op.create_index(
        "ix_core_provider_export_scope", "core_ai_provider_export_snapshots",
        ["tenant_id", "unit_id", "request_id"],
    )


def downgrade() -> None:
    # Only on disposable testing databases; would destroy source history.
    op.drop_index("ix_core_provider_export_scope", "core_ai_provider_export_snapshots")
    op.drop_table("core_ai_provider_export_snapshots")
