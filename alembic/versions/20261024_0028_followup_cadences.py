"""F7 durable versioned cadence plans, scheduled internal tasks and event journal."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024_0028"
down_revision = "20261024_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_cadence_definitions",
        sa.Column("cadence_id", sa.String(64), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("steps_ciphertext", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_cadence_def_scope", "assistant_cadence_definitions",
        ["tenant_id", "unit_id"],
    )
    op.create_table(
        "assistant_cadence_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("cadence_id", sa.String(64), nullable=False),
        sa.Column("cadence_version", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_contacts.contact_id"), nullable=False),
        sa.Column("opportunity_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_opportunities.opportunity_id"),
                  nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "unit_id", "idempotency_key",
            name="uq_cadence_run_idempotency",
        ),
    )
    op.create_index(
        "ix_cadence_run_scope", "assistant_cadence_runs",
        ["tenant_id", "unit_id", "contact_id"],
    )
    op.create_table(
        "assistant_cadence_jobs",
        sa.Column("job_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64),
                  sa.ForeignKey("assistant_cadence_runs.run_id"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_generation", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(48)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "step_index", name="uq_cadence_job_step"),
    )
    op.create_index(
        "ix_cadence_due", "assistant_cadence_jobs",
        ["state", "available_at"],
    )
    op.create_table(
        "assistant_cadence_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("run_id", sa.String(64),
                  sa.ForeignKey("assistant_cadence_runs.run_id"), nullable=False),
        sa.Column("job_id", sa.String(64)),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(48)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_cadence_events_scope", "assistant_cadence_events",
        ["tenant_id", "unit_id", "run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cadence_events_scope", table_name="assistant_cadence_events")
    op.drop_table("assistant_cadence_events")
    op.drop_index("ix_cadence_due", table_name="assistant_cadence_jobs")
    op.drop_table("assistant_cadence_jobs")
    op.drop_index("ix_cadence_run_scope", table_name="assistant_cadence_runs")
    op.drop_table("assistant_cadence_runs")
    op.drop_index("ix_cadence_def_scope", table_name="assistant_cadence_definitions")
    op.drop_table("assistant_cadence_definitions")
