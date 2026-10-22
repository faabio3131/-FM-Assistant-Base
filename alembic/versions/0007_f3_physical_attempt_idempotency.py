"""Persist physical provider attempt identities for F3 FinOps idempotency.

Revision ID: f3_0007
Revises: f3_0006

The column is nullable so historical ledger rows are never rewritten or
assigned a synthetic physical identity. New Core events retain their real
router-generated attempt IDs and are unique per tenant/unit/request.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3_0007"
down_revision = "f3_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("core_ai_usage_events", sa.Column(
        "attempt_id", sa.String(128), nullable=True,
    ))
    op.create_index(
        "uq_core_ai_usage_physical_attempt", "core_ai_usage_events",
        ["tenant_id", "unit_id", "request_id", "attempt_id"], unique=True,
    )


def downgrade() -> None:
    # Only safe in disposable internal CI databases.
    op.drop_index("uq_core_ai_usage_physical_attempt", table_name="core_ai_usage_events")
    op.drop_column("core_ai_usage_events", "attempt_id")
