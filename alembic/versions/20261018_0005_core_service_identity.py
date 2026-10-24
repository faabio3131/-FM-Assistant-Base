"""Add gated Core-to-Assistant service identity and replay ledger.

Revision ID: 20261018_0005
Revises: 20261018_0004

Identity/grant provisioning is a separate approved operation.
Migration DOES NOT create, enable or distribute service credentials.
"""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0005"
down_revision = "20261018_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_core_bridge_identities",
        sa.Column("key_id", sa.String(64), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "assistant_core_bridge_grants",
        sa.Column("key_id", sa.String(64), sa.ForeignKey(
            "assistant_core_bridge_identities.key_id"), primary_key=True),
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("unit_id", sa.String(128), primary_key=True),
        sa.Column("capability", sa.String(160), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
        ),
    )
    op.create_table(
        "assistant_core_bridge_access",
        sa.Column("key_id", sa.String(64), sa.ForeignKey(
            "assistant_core_bridge_identities.key_id"), primary_key=True),
        sa.Column("nonce", sa.String(96), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(160), nullable=False),
        sa.Column("connection_id", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_core_bridge_access_time",
        "assistant_core_bridge_access", ["created_at"])
    op.create_index(
        "ix_assistant_core_bridge_access_scope",
        "assistant_core_bridge_access",
        ["tenant_id", "unit_id", "created_at"])


def downgrade() -> None:
    # Destructive; only for disposable test database, never automatic production rollback.
    op.drop_index("ix_assistant_core_bridge_access_scope", table_name="assistant_core_bridge_access")
    op.drop_index("ix_assistant_core_bridge_access_time", table_name="assistant_core_bridge_access")
    op.drop_table("assistant_core_bridge_access")
    op.drop_table("assistant_core_bridge_grants")
    op.drop_table("assistant_core_bridge_identities")
