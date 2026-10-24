"""Append-only audit for Command bridge service authority.

Revision ID: 20261018_0006
Revises: 20261018_0005
No live secret, identity or grant is provisioned by this migration.
"""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0006"
down_revision = "20261018_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_command_bridge_control_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(96), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(160), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.String(128), nullable=False),
        sa.Column("command_request_id", sa.String(96), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "nonce", name="uq_assistant_command_bridge_control_nonce"
        ),
    )


def downgrade() -> None:
    # Destructive: allowed only on disposable test databases.
    op.drop_table("assistant_command_bridge_control_events")
