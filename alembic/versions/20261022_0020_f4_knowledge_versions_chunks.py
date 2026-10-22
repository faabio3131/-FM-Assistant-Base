"""F4 append-only knowledge source revisions and bounded text chunks.

Revision ID: 20261022_0020
Revises: 20261020_0019
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261022_0020"
down_revision = "20261020_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_knowledge_source_versions",
        sa.Column("document_id", sa.String(64),
                  sa.ForeignKey("assistant_knowledge_documents.document_id",
                                ondelete="CASCADE"), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(512), nullable=True),
        sa.Column("actor_credential_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_knowledge_version_scope",
        "assistant_knowledge_source_versions",
        ["tenant_id", "unit_id", "document_id"],
    )
    op.create_table(
        "assistant_knowledge_chunks",
        sa.Column("document_id", sa.String(64), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id", "revision"],
            ["assistant_knowledge_source_versions.document_id",
             "assistant_knowledge_source_versions.revision"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_assistant_knowledge_chunk_scope",
        "assistant_knowledge_chunks",
        ["tenant_id", "unit_id", "document_id", "revision"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_knowledge_chunk_scope", table_name="assistant_knowledge_chunks")
    op.drop_table("assistant_knowledge_chunks")
    op.drop_index(
        "ix_assistant_knowledge_version_scope",
        table_name="assistant_knowledge_source_versions",
    )
    op.drop_table("assistant_knowledge_source_versions")
