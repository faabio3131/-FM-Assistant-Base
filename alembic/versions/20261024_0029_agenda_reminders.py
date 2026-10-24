"""F7 agenda and private reminder tasks, additive over cadence schema 0028."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024_0029"
down_revision = "20261024_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_agenda_appointments",
        sa.Column("appointment_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("owner_user_id", sa.String(64), nullable=False),
        sa.Column("contact_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_contacts.contact_id"), nullable=False),
        sa.Column("opportunity_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_opportunities.opportunity_id"),
                  nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("title_ciphertext", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remind_minutes", sa.Integer(), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True)),
        sa.Column("reminder_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "unit_id", "idempotency_key",
            name="uq_agenda_appointment_idempotency",
        ),
    )
    op.create_index(
        "ix_agenda_owner_range", "assistant_agenda_appointments",
        ["tenant_id", "unit_id", "owner_user_id", "status", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_agenda_reminders", "assistant_agenda_appointments",
        ["status", "remind_at"],
    )
    op.create_table(
        "assistant_agenda_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("appointment_id", sa.String(64),
                  sa.ForeignKey("assistant_agenda_appointments.appointment_id"),
                  nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agenda_events_scope", "assistant_agenda_events",
        ["tenant_id", "unit_id", "appointment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agenda_events_scope", table_name="assistant_agenda_events")
    op.drop_table("assistant_agenda_events")
    op.drop_index("ix_agenda_reminders", table_name="assistant_agenda_appointments")
    op.drop_index("ix_agenda_owner_range", table_name="assistant_agenda_appointments")
    op.drop_table("assistant_agenda_appointments")
