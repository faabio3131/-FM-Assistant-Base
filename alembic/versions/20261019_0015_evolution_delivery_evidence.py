"""Correlated provider delivery status evidence (no raw webhook storage).

Revision ID: 20261019_0015
Revises: 20261019_0014
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261019_0015"
down_revision = "20261019_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assistant_evolution_inbound_jobs") as batch:
        batch.add_column(sa.Column("delivery_status", sa.String(32), nullable=True))
        batch.add_column(sa.Column("delivery_evidence_sha256", sa.String(64), nullable=True))
        batch.add_column(sa.Column("delivery_observed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Destructive rollback for disposable test databases only.
    with op.batch_alter_table("assistant_evolution_inbound_jobs") as batch:
        batch.drop_column("delivery_observed_at")
        batch.drop_column("delivery_evidence_sha256")
        batch.drop_column("delivery_status")
