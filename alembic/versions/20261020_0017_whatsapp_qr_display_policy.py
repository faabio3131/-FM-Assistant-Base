"""Read-only FM-corporate QR display policy projection.

Revision ID: 20261020_0017
Revises: 20261019_0016
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261020_0017"
down_revision = "20261019_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_whatsapp_qr_display_policy",
        sa.Column("product_code", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("display_seconds", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_seconds BETWEEN 15 AND 120",
            name="assistant_whatsapp_qr_display_seconds_ck",
        ),
        sa.CheckConstraint(
            "revision >= 1", name="assistant_whatsapp_qr_display_revision_ck",
        ),
    )


def downgrade() -> None:
    # Destructive rollback allowed ONLY in disposable test databases.
    op.drop_table("assistant_whatsapp_qr_display_policy")
