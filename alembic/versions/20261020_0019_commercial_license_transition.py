"""FM commercial lifecycle audit; security holds use a separate authority.

Revision ID: 20261020_0019
Revises: 20261020_0018
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261020_0019"
down_revision = "20261020_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_commercial_license_transition_audit",
        sa.Column("command_request_id", sa.String(128), primary_key=True),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(96), nullable=False),
        sa.Column("tenant_id", sa.String(128),
                  sa.ForeignKey("assistant_tenants.tenant_id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("expected_status", sa.String(32), nullable=False),
        sa.Column("result_status", sa.String(32), nullable=False),
        sa.Column("old_plan_code", sa.String(120), nullable=False),
        sa.Column("old_plan_revision", sa.Integer(), nullable=False),
        sa.Column("new_plan_code", sa.String(120), nullable=False),
        sa.Column("new_plan_revision", sa.Integer(), nullable=False),
        sa.Column("old_valid_until", sa.BigInteger(), nullable=False),
        sa.Column("new_valid_until", sa.BigInteger(), nullable=False),
        sa.Column("verified_payment_ref", sa.String(128), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_commercial_license_transition_tenant",
        "assistant_commercial_license_transition_audit", ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_commercial_license_transition_tenant")
    op.drop_table("assistant_commercial_license_transition_audit")
