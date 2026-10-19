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
    op.add_column("assistant_evolution_inbound_jobs", sa.Column("outbound_operation_id", sa.String(64), nullable=True))
    op.add_column("assistant_evolution_inbound_jobs", sa.Column("outbound_status", sa.String(32), nullable=True))
    op.add_column("assistant_evolution_inbound_jobs", sa.Column("outbound_reference", sa.String(160), nullable=True))
    op.add_column("assistant_evolution_inbound_jobs", sa.Column("send_started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_assistant_evolution_job_outbound_status",
        "assistant_evolution_inbound_jobs",
        "outbound_status IS NULL OR outbound_status IN ('uncertain', 'provider_acknowledged')",
    )
    op.execute(
        "ALTER TABLE assistant_evolution_inbound_jobs DROP CONSTRAINT "
        "ck_assistant_evolution_job_state"
    ) if op.get_bind().dialect.name == "postgresql" else None
    if op.get_bind().dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_assistant_evolution_job_state",
            "assistant_evolution_inbound_jobs",
            "state IN ('pending','processing','sending','complete','reconcile_required','reviewed')",
        )


def downgrade() -> None:
    op.drop_constraint("ck_assistant_evolution_job_outbound_status", "assistant_evolution_inbound_jobs", type_="check")
    op.drop_column("assistant_evolution_inbound_jobs", "send_started_at")
    op.drop_column("assistant_evolution_inbound_jobs", "outbound_reference")
    op.drop_column("assistant_evolution_inbound_jobs", "outbound_status")
    op.drop_column("assistant_evolution_inbound_jobs", "outbound_operation_id")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_assistant_evolution_job_state", "assistant_evolution_inbound_jobs", type_="check")
        op.create_check_constraint(
            "ck_assistant_evolution_job_state",
            "assistant_evolution_inbound_jobs",
            "state IN ('pending','processing','complete','reconcile_required','reviewed')",
        )
