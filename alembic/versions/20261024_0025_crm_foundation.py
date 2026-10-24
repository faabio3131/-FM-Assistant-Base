"""F6 first vertical slice: tenant-scoped CRM contacts, opportunities and audit."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024_0025"
down_revision = "20261023_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_crm_contacts",
        sa.Column("contact_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email_ciphertext", sa.Text(), nullable=True),
        sa.Column("email_fingerprint", sa.String(64), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "unit_id", "email_fingerprint",
                            name="uq_crm_contact_email_scope"),
    )
    op.create_index("ix_crm_contacts_scope", "assistant_crm_contacts",
                    ["tenant_id", "unit_id", "created_at"])
    op.create_table(
        "assistant_crm_opportunities",
        sa.Column("opportunity_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("contact_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_contacts.contact_id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crm_opportunity_scope", "assistant_crm_opportunities",
                    ["tenant_id", "unit_id", "stage", "created_at"])
    op.create_table(
        "assistant_crm_audit",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("entity_kind", sa.String(24), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_stage", sa.String(24), nullable=True),
        sa.Column("to_stage", sa.String(24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("assistant_crm_audit")
    op.drop_index("ix_crm_opportunity_scope", table_name="assistant_crm_opportunities")
    op.drop_table("assistant_crm_opportunities")
    op.drop_index("ix_crm_contacts_scope", table_name="assistant_crm_contacts")
    op.drop_table("assistant_crm_contacts")
