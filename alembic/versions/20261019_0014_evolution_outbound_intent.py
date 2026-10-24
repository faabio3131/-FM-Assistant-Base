"""Durable outbound intent and provider reconciliation metadata.

Revision ID: 20261019_0014
Revises: 20261019_0013
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261019_0014"
down_revision = "20261019_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite test databases require batch table recreation for named checks.
    with op.batch_alter_table("assistant_evolution_inbound_jobs", recreate="auto") as batch:
        batch.add_column(sa.Column("outbound_operation_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("outbound_status", sa.String(32), nullable=True))
        batch.add_column(sa.Column("outbound_reference", sa.String(160), nullable=True))
        batch.add_column(sa.Column("send_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.drop_constraint("ck_assistant_evolution_job_state", type_="check")
        batch.create_check_constraint(
            "ck_assistant_evolution_job_state",
            "state IN ('pending','processing','sending','complete','reconcile_required','reviewed')",
        )
        batch.create_check_constraint(
            "ck_assistant_evolution_job_outbound_status",
            "outbound_status IS NULL OR outbound_status IN ('uncertain','provider_acknowledged')",
        )


def downgrade() -> None:
    # For disposable test DB only. Never execute destructive downgrade in production.
    with op.batch_alter_table("assistant_evolution_inbound_jobs", recreate="auto") as batch:
        batch.drop_constraint("ck_assistant_evolution_job_outbound_status", type_="check")
        batch.drop_constraint("ck_assistant_evolution_job_state", type_="check")
        batch.create_check_constraint(
            "ck_assistant_evolution_job_state",
            "state IN ('pending','processing','complete','reconcile_required','reviewed')",
        )
        batch.drop_column("send_started_at")
        batch.drop_column("outbound_reference")
        batch.drop_column("outbound_status")
        batch.drop_column("outbound_operation_id")
