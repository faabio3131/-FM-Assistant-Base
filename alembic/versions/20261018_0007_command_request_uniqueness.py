"""Enforce one canonical terminal event per Command mutation request ID.

Revision ID: 20261018_0007
Revises: 20261018_0006

Only an additive unique index; no credentials, identities or grants are created.
A duplicate in a previously provisioned environment stops migration instead of
silently deleting, merging or rewriting audit evidence.
"""

from alembic import op

revision = "20261018_0007"
down_revision = "20261018_0006"
branch_labels = None
depends_on = None

INDEX = "uq_assistant_command_bridge_control_request_id"
TABLE = "assistant_command_bridge_control_events"


def upgrade() -> None:
    op.create_index(INDEX, TABLE, ["command_request_id"], unique=True)


def downgrade() -> None:
    # Only for disposable test DBs; never automatically downgrade production.
    op.drop_index(INDEX, table_name=TABLE)
