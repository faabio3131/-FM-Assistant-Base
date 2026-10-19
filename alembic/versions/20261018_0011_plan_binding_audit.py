"""Immutable audit for Command-signed tenant plan binding.

Revision ID: 20261018_0011
Revises: 20261018_0010
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261018_0011"
down_revision = "20261018_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_plan_binding_audit",
        sa.Column("key_id", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(96), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("old_plan_code", sa.String(120), nullable=False),
        sa.Column("plan_code", sa.String(120), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["assistant_tenants.tenant_id"], ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_assistant_plan_binding_audit_tenant_id",
        "assistant_plan_binding_audit", ["tenant_id"],
    )


def downgrade() -> None:
    # Destructive downgrade permitted in disposable test databases only.
    op.drop_index(
        "ix_assistant_plan_binding_audit_tenant_id",
        table_name="assistant_plan_binding_audit",
    )
    op.drop_table("assistant_plan_binding_audit")
