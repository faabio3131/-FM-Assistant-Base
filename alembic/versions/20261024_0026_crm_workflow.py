"""F6 governed links, qualification, proposal snapshots and activities."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024_0026"
down_revision = "20261024_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_crm_conversation_links",
        sa.Column("conversation_id", sa.String(64),
                  sa.ForeignKey("assistant_conversations.conversation_id"), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("contact_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_contacts.contact_id"), nullable=False),
        sa.Column("opportunity_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_opportunities.opportunity_id")),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("linked_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crm_links_contact_scope", "assistant_crm_conversation_links",
                    ["tenant_id", "unit_id", "contact_id"])
    op.create_index("ix_crm_links_opportunity_scope", "assistant_crm_conversation_links",
                    ["tenant_id", "unit_id", "opportunity_id"])
    op.create_table(
        "assistant_crm_qualifications",
        sa.Column("opportunity_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_opportunities.opportunity_id"), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("need_confirmed", sa.Boolean(), nullable=False),
        sa.Column("budget_confirmed", sa.Boolean(), nullable=False),
        sa.Column("decision_maker_confirmed", sa.Boolean(), nullable=False),
        sa.Column("timeline_days", sa.Integer()),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assistant_crm_proposals",
        sa.Column("proposal_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("opportunity_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_opportunities.opportunity_id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("terms_ciphertext", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crm_proposals_scope", "assistant_crm_proposals",
                    ["tenant_id", "unit_id", "opportunity_id"])
    op.create_table(
        "assistant_crm_activities",
        sa.Column("activity_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("opportunity_id", sa.String(64),
                  sa.ForeignKey("assistant_crm_opportunities.opportunity_id"), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("details_ciphertext", sa.Text()),
        sa.Column("related_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crm_activities_scope", "assistant_crm_activities",
                    ["tenant_id", "unit_id", "opportunity_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_crm_activities_scope", table_name="assistant_crm_activities")
    op.drop_table("assistant_crm_activities")
    op.drop_index("ix_crm_proposals_scope", table_name="assistant_crm_proposals")
    op.drop_table("assistant_crm_proposals")
    op.drop_table("assistant_crm_qualifications")
    op.drop_index("ix_crm_links_opportunity_scope", table_name="assistant_crm_conversation_links")
    op.drop_index("ix_crm_links_contact_scope", table_name="assistant_crm_conversation_links")
    op.drop_table("assistant_crm_conversation_links")
