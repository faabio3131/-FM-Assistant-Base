"""Persist command-signed plan catalog nonces.

Revision ID: 20261018_0010
Revises: 20261018_0009
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261018_0010"
down_revision = "20261018_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_plan_sync_nonces",
        sa.Column("key_id", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(96), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    # Test-only destructive downgrade; not for any persistent database.
    op.drop_table("assistant_plan_sync_nonces")
