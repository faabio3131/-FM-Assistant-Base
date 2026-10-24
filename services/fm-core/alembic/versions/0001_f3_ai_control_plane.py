"""F3 AI Control Plane foundation, additive migration.

Revision ID: f3_0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_ai_providers",
        sa.Column("provider_id", sa.String(128), primary_key=True),
        sa.Column("adapter", sa.String(40), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "core_ai_models",
        sa.Column("model_id", sa.String(128), primary_key=True),
        sa.Column(
            "provider_id", sa.String(128),
            sa.ForeignKey("core_ai_providers.provider_id"), nullable=False,
        ),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "core_ai_model_capabilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "model_id", sa.String(128),
            sa.ForeignKey("core_ai_models.model_id"), nullable=False,
        ),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.UniqueConstraint("model_id", "capability"),
    )
    op.create_table(
        "core_ai_route_policies",
        sa.Column("policy_id", sa.String(128), primary_key=True),
        sa.Column("scope", sa.String(12), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=True),
        sa.Column("unit_id", sa.String(128), nullable=True),
        sa.Column(
            "model_id", sa.String(128),
            sa.ForeignKey("core_ai_models.model_id"), nullable=False,
        ),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("price_snapshot_id", sa.String(128), nullable=False),
        sa.Column("credential_source", sa.String(20), nullable=False),
        sa.Column("secret_reference", sa.String(512), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "core_ai_provider_health",
        sa.Column(
            "provider_id", sa.String(128),
            sa.ForeignKey("core_ai_providers.provider_id"), primary_key=True,
        ),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("circuit", sa.String(12), nullable=False),
    )
    op.create_table(
        "core_ai_price_snapshots",
        sa.Column("price_snapshot_id", sa.String(128), primary_key=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("modalidade", sa.String(40), nullable=False),
        sa.Column("moeda", sa.String(3), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("vigencia_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vigencia_fim", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "core_ai_price_tariffs",
        sa.Column("tariff_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "price_snapshot_id", sa.String(128),
            sa.ForeignKey("core_ai_price_snapshots.price_snapshot_id"), nullable=False,
        ),
        sa.Column("componente", sa.String(80), nullable=False),
        sa.Column("preco_decimal", sa.String(80), nullable=False),
        sa.Column("unidades_por_preco", sa.Integer(), nullable=False),
    )
    op.create_table(
        "core_ai_usage_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("unit_id", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("route_reason", sa.String(500), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("fallback_reason", sa.String(200), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("cost_decimal", sa.String(80), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("cost_origin", sa.String(40), nullable=False),
        sa.Column("price_snapshot_id", sa.String(128), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_core_ai_usage_events_tenant_id", "core_ai_usage_events", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_core_ai_usage_events_tenant_id", table_name="core_ai_usage_events")
    op.drop_table("core_ai_usage_events")
    op.drop_table("core_ai_price_tariffs")
    op.drop_table("core_ai_price_snapshots")
    op.drop_table("core_ai_provider_health")
    op.drop_table("core_ai_route_policies")
    op.drop_table("core_ai_model_capabilities")
    op.drop_table("core_ai_models")
    op.drop_table("core_ai_providers")
