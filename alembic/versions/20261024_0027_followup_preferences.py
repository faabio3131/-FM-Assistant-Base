"""F7 tenant-scoped contact suppression and quiet hours; no outbound automation."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024_0027"
down_revision = "20261024_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_followup_preferences",
        sa.Column("preference_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("contact_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_contacts.contact_id"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("opted_out", sa.Boolean(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("quiet_start_minute", sa.Integer(), nullable=False),
        sa.Column("quiet_end_minute", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "unit_id", "contact_id", "channel",
            name="uq_followup_policy_scope_contact_channel",
        ),
    )
    op.create_index(
        "ix_followup_policy_scope", "assistant_followup_preferences",
        ["tenant_id", "unit_id", "contact_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_followup_policy_scope", table_name="assistant_followup_preferences",
    )
    op.drop_table("assistant_followup_preferences")
