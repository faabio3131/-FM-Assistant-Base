"""Add identity, tenancy, RBAC, sessions, license and entitlements.

Revision ID: 20261017_0003
Revises: 20261003_0002
Create Date: 2026-10-17
"""

import sqlalchemy as sa

from alembic import op

revision = "20261017_0003"
down_revision = "20261003_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_tenants",
        sa.Column("tenant_id", sa.String(length=128), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_assistant_tenants_slug"),
    )

    op.create_table(
        "assistant_units",
        sa.Column(
            "tenant_id",
            sa.String(length=128),
            sa.ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("unit_id", sa.String(length=128), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "assistant_users",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_users_email", "assistant_users", ["email"], unique=True)

    op.create_table(
        "assistant_memberships",
        sa.Column("membership_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=128),
            sa.ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            name="uq_assistant_membership_tenant_user",
        ),
    )
    op.create_index(
        "ix_assistant_memberships_tenant_id",
        "assistant_memberships",
        ["tenant_id"],
    )
    op.create_index(
        "ix_assistant_memberships_user_id",
        "assistant_memberships",
        ["user_id"],
    )

    op.create_table(
        "assistant_membership_units",
        sa.Column(
            "membership_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_memberships.membership_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.String(length=128), primary_key=True),
        sa.Column("unit_id", sa.String(length=128), primary_key=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "assistant_sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "membership_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_memberships.membership_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("active_unit_id", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "active_unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_assistant_sessions_user_id", "assistant_sessions", ["user_id"])
    op.create_index(
        "ix_assistant_sessions_membership_id",
        "assistant_sessions",
        ["membership_id"],
    )
    op.create_index(
        "ix_assistant_sessions_token_hash",
        "assistant_sessions",
        ["token_hash"],
        unique=True,
    )

    op.create_table(
        "assistant_invitations",
        sa.Column("invitation_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_assistant_invitations_tenant_id",
        "assistant_invitations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_assistant_invitations_email",
        "assistant_invitations",
        ["email"],
    )
    op.create_index(
        "ix_assistant_invitations_token_hash",
        "assistant_invitations",
        ["token_hash"],
        unique=True,
    )

    op.create_table(
        "assistant_password_resets",
        sa.Column("reset_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(length=128),
            sa.ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_password_resets_user_id",
        "assistant_password_resets",
        ["user_id"],
    )
    op.create_index(
        "ix_assistant_password_resets_tenant_id",
        "assistant_password_resets",
        ["tenant_id"],
    )
    op.create_index(
        "ix_assistant_password_resets_token_hash",
        "assistant_password_resets",
        ["token_hash"],
        unique=True,
    )

    op.create_table(
        "assistant_tenant_licenses",
        sa.Column(
            "tenant_id",
            sa.String(length=128),
            sa.ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("plan_code", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "assistant_entitlements",
        sa.Column(
            "tenant_id",
            sa.String(length=128),
            sa.ForeignKey("assistant_tenants.tenant_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("capability", sa.String(length=160), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    tenant_scope = """
        SELECT tenant_id FROM assistant_tenant_credentials
        UNION
        SELECT tenant_id FROM assistant_personas
        UNION
        SELECT tenant_id FROM assistant_conversations
        UNION
        SELECT tenant_id FROM assistant_knowledge_documents
        UNION
        SELECT tenant_id FROM assistant_whatsapp_channels
    """
    unit_scope = """
        SELECT tenant_id, unit_id FROM assistant_tenant_credentials
        UNION
        SELECT tenant_id, unit_id FROM assistant_personas
        UNION
        SELECT tenant_id, unit_id FROM assistant_conversations
        UNION
        SELECT tenant_id, unit_id FROM assistant_knowledge_documents
        UNION
        SELECT tenant_id, unit_id FROM assistant_whatsapp_channels
    """

    op.execute(
        sa.text(
            f"""
            INSERT INTO assistant_tenants
                (tenant_id, display_name, slug, status, created_at, updated_at)
            SELECT tenant_id, tenant_id, tenant_id, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM ({tenant_scope}) AS scopes
            WHERE tenant_id IS NOT NULL AND tenant_id <> ''
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO assistant_units
                (tenant_id, unit_id, display_name, status, created_at, updated_at)
            SELECT tenant_id, unit_id, unit_id, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM ({unit_scope}) AS scopes
            WHERE tenant_id IS NOT NULL AND tenant_id <> ''
              AND unit_id IS NOT NULL AND unit_id <> ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO assistant_tenant_licenses
                (tenant_id, plan_code, status, trial_started_at, trial_ends_at,
                 period_started_at, period_ends_at, created_at, updated_at)
            SELECT tenant_id, 'legacy_foundation', 'active', NULL, NULL,
                   NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM assistant_tenants
            """
        )
    )


def downgrade() -> None:
    op.drop_table("assistant_entitlements")
    op.drop_table("assistant_tenant_licenses")

    op.drop_index("ix_assistant_password_resets_token_hash", table_name="assistant_password_resets")
    op.drop_index("ix_assistant_password_resets_tenant_id", table_name="assistant_password_resets")
    op.drop_index("ix_assistant_password_resets_user_id", table_name="assistant_password_resets")
    op.drop_table("assistant_password_resets")

    op.drop_index(
        "ix_assistant_invitations_token_hash",
        table_name="assistant_invitations",
    )
    op.drop_index("ix_assistant_invitations_email", table_name="assistant_invitations")
    op.drop_index(
        "ix_assistant_invitations_tenant_id",
        table_name="assistant_invitations",
    )
    op.drop_table("assistant_invitations")

    op.drop_index("ix_assistant_sessions_token_hash", table_name="assistant_sessions")
    op.drop_index("ix_assistant_sessions_membership_id", table_name="assistant_sessions")
    op.drop_index("ix_assistant_sessions_user_id", table_name="assistant_sessions")
    op.drop_table("assistant_sessions")

    op.drop_table("assistant_membership_units")

    op.drop_index("ix_assistant_memberships_user_id", table_name="assistant_memberships")
    op.drop_index("ix_assistant_memberships_tenant_id", table_name="assistant_memberships")
    op.drop_table("assistant_memberships")

    op.drop_index("ix_assistant_users_email", table_name="assistant_users")
    op.drop_table("assistant_users")

    op.drop_table("assistant_units")
    op.drop_table("assistant_tenants")
