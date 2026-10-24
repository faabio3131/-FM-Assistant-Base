"""Append-only FM corporate license security hold evidence.

Revision ID: 20261020_0018
Revises: 20261020_0017
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261020_0018"
down_revision = "20261020_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_license_security_hold_audit",
        sa.Column("key_id", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(96), primary_key=True),
        sa.Column("command_request_id", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "tenant_id", sa.String(128),
            sa.ForeignKey("assistant_tenants.tenant_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("plan_code", sa.String(120), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("old_status", sa.String(32), nullable=False),
        sa.Column("expected_valid_until", sa.BigInteger(), nullable=False),
        sa.Column("held_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "plan_revision >= 1",
            name="assistant_license_security_hold_plan_revision_ck",
        ),
    )
    op.create_index(
        "ix_assistant_license_security_hold_tenant",
        "assistant_license_security_hold_audit", ["tenant_id"],
    )


def downgrade() -> None:
    # Only disposable test databases may run destructive rollback.
    op.drop_index("ix_assistant_license_security_hold_tenant")
    op.drop_table("assistant_license_security_hold_audit")
