"""F3 additive immutable FM provider evidence references.

Revision ID: f3_0005
Revises: f3_0004
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3_0005"
down_revision = "f3_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_ai_provider_evidence",
        sa.Column("evidence_id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.String(80), nullable=True),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("no_charge", sa.Boolean(), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("canonical_sha256", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("input_tokens >= 0", name="ck_evidence_input_nonnegative"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_evidence_output_nonnegative"),
    )
    op.create_index(
        "ix_core_evidence_scope",
        "core_ai_provider_evidence",
        ["tenant_id", "unit_id", "request_id"],
    )


def downgrade() -> None:
    # Destructive: disposable CI databases only.
    op.drop_index("ix_core_evidence_scope", table_name="core_ai_provider_evidence")
    op.drop_table("core_ai_provider_evidence")
