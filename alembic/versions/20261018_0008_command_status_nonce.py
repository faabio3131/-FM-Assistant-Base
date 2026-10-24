"""Add durable replay protection for Command status HMAC requests.

Revision ID: 20261018_0008
Revises: 20261018_0007

Additive-only; no live credentials or grants.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261018_0008"
down_revision = "20261018_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_command_bridge_status_nonce",
        sa.Column("nonce", sa.String(96), primary_key=True),
        sa.Column("command_request_id", sa.String(96), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    # Destructive downgrade is restricted to isolated disposable test databases.
    op.drop_table("assistant_command_bridge_status_nonce")
