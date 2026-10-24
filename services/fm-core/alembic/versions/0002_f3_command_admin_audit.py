"""F3.6.2 Command administrative audit ledger (additive).

Revision ID: f3_0002
Revises: f3_0001
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3_0002"
down_revision = "f3_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_ai_admin_mutation_audit",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("token_jti", sa.String(128), nullable=False),
        sa.Column("actor_user_id", sa.String(128), nullable=False),
        sa.Column("actor_session_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_id", sa.String(256), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "token_jti", name="uq_core_ai_admin_mutation_token_jti"
        ),
    )


def downgrade() -> None:
    # Downgrade is permitted only in a disposable environment; records are lost.
    op.drop_table("core_ai_admin_mutation_audit")
