"""Initial standalone FM Assistant SaaS schema.

Revision ID: 20261003_0001
Revises:
Create Date: 2026-10-03
"""

from alembic import op

from fm_assistant.db import Base

revision = "20261003_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
