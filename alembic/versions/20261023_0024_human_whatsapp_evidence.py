"""F5 provider-authoritative delivery state and operator review candidates."""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261023_0024"
down_revision = "20261023_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    t = "assistant_human_whatsapp_outbox"
    op.add_column(t, sa.Column("delivery_status", sa.String(24), nullable=True))
    op.add_column(t, sa.Column("delivery_evidence_sha256", sa.String(64), nullable=True))
    op.add_column(t, sa.Column("delivery_observed_at",
                               sa.DateTime(timezone=True), nullable=True))
    op.add_column(t, sa.Column("candidate_reference", sa.String(160), nullable=True))
    op.add_column(t, sa.Column("candidate_evidence_sha256", sa.String(64), nullable=True))
    op.add_column(t, sa.Column("candidate_observed_at",
                               sa.DateTime(timezone=True), nullable=True))
    op.add_column(t, sa.Column("reviewed_by", sa.String(64), nullable=True))
    op.add_column(t, sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_human_whatsapp_provider_receipt", t,
                    ["connection_id", "provider_reference"])


def downgrade() -> None:
    t = "assistant_human_whatsapp_outbox"
    op.drop_index("ix_human_whatsapp_provider_receipt", table_name=t)
    for c in ("reviewed_at", "reviewed_by", "candidate_observed_at",
              "candidate_evidence_sha256", "candidate_reference",
              "delivery_observed_at", "delivery_evidence_sha256", "delivery_status"):
        op.drop_column(t, c)
