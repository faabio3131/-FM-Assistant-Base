"""Evidence investigation metadata, never an authorization to resend.

Revision ID: 20261019_0016
Revises: 20261019_0015
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261019_0016"
down_revision = "20261019_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assistant_evolution_inbound_jobs") as batch:
        batch.add_column(sa.Column("evidence_candidate_reference", sa.String(160), nullable=True))
        batch.add_column(sa.Column("evidence_candidate_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("evidence_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Destructive: disposable CI databases only.
    with op.batch_alter_table("assistant_evolution_inbound_jobs") as batch:
        batch.drop_column("evidence_requested_at")
        batch.drop_column("evidence_candidate_digest")
        batch.drop_column("evidence_candidate_reference")
