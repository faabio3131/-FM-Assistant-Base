"""Add universal integration and credential control plane.

Revision ID: 20261018_0004
Revises: 20261017_0003
Create Date: 2026-10-18
"""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0004"
down_revision = "20261017_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_integration_providers",
        sa.Column("provider_key", sa.String(length=120), primary_key=True),
        sa.Column("integration_type", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "assistant_integration_connections",
        sa.Column("connection_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column(
            "provider_key",
            sa.String(length=120),
            sa.ForeignKey("assistant_integration_providers.provider_key"),
            nullable=False,
        ),
        sa.Column("integration_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_assistant_integration_connections_tenant_id",
        "assistant_integration_connections",
        ["tenant_id"],
    )
    op.create_index(
        "ix_assistant_integration_connections_provider_key",
        "assistant_integration_connections",
        ["provider_key"],
    )
    op.create_index(
        "ix_assistant_integration_scope",
        "assistant_integration_connections",
        ["tenant_id", "unit_id", "provider_key", "status"],
    )

    op.create_table(
        "assistant_integration_secret_versions",
        sa.Column(
            "connection_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("secret_name", sa.String(length=120), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("storage_backend", sa.String(length=64), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=True),
        sa.Column("secret_reference", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_integration_secret_active",
        "assistant_integration_secret_versions",
        ["connection_id", "secret_name", "active"],
    )

    op.create_table(
        "assistant_integration_capabilities",
        sa.Column(
            "connection_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("capability", sa.String(length=160), primary_key=True),
    )

    op.create_table(
        "assistant_integration_inbound",
        sa.Column(
            "connection_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("message_id", sa.String(length=160), primary_key=True),
        sa.Column("sender_hash", sa.String(length=64), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("outbound_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_integration_inbound_status",
        "assistant_integration_inbound",
        ["connection_id", "status", "updated_at"],
    )

    op.create_table(
        "assistant_integration_validations",
        sa.Column("validation_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("code", sa.String(length=160), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_integration_validations_connection_id",
        "assistant_integration_validations",
        ["connection_id"],
    )
    op.create_index(
        "ix_assistant_integration_validation_latest",
        "assistant_integration_validations",
        ["connection_id", "created_at"],
    )

    op.create_table(
        "assistant_integration_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(length=64),
            sa.ForeignKey("assistant_integration_connections.connection_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_assistant_integration_events_connection_id",
        "assistant_integration_events",
        ["connection_id"],
    )
    op.create_index(
        "ix_assistant_integration_event_scope",
        "assistant_integration_events",
        ["tenant_id", "unit_id", "created_at"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO assistant_integration_providers
                (provider_key, integration_type, display_name, definition_version,
                 enabled, created_at, updated_at)
            VALUES
                ('whatsapp_meta', 'whatsapp', 'WhatsApp Cloud API (Meta)', 1,
                 TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO assistant_integration_connections
                (connection_id, tenant_id, unit_id, provider_key, integration_type,
                 status, config_json, revision, created_at, updated_at)
            SELECT
                channel_id,
                tenant_id,
                unit_id,
                'whatsapp_meta',
                'whatsapp',
                CASE WHEN enabled THEN 'active' ELSE 'disabled' END,
                '{"phone_number_id":"' || phone_number_id ||
                '","business_account_id":' ||
                CASE
                    WHEN business_account_id IS NULL THEN 'null'
                    ELSE '"' || business_account_id || '"'
                END ||
                ',"graph_api_version":"' || graph_api_version || '"}',
                1,
                created_at,
                updated_at
            FROM assistant_whatsapp_channels
            """
        )
    )

    for secret_name, source_column in (
        ("access_token", "access_token_ciphertext"),
        ("app_secret", "app_secret_ciphertext"),
        ("verify_token", "verify_token_ciphertext"),
    ):
        op.execute(
            sa.text(
                f"""
                INSERT INTO assistant_integration_secret_versions
                    (connection_id, secret_name, version, source, storage_backend,
                     ciphertext, secret_reference, active, expires_at, revoked_at, created_at)
                SELECT
                    channel_id,
                    '{secret_name}',
                    1,
                    'tenant_managed',
                    'db_encrypted',
                    {source_column},
                    NULL,
                    TRUE,
                    NULL,
                    NULL,
                    created_at
                FROM assistant_whatsapp_channels
                """
            )
        )

    op.execute(
        sa.text(
            """
            INSERT INTO assistant_integration_inbound
                (connection_id, message_id, sender_hash, message_type, status,
                 outbound_id, error_code, created_at, updated_at)
            SELECT
                channel_id, message_id, sender_hash, message_type, status,
                outbound_id, error_code, created_at, updated_at
            FROM assistant_whatsapp_inbound
            """
        )
    )

    for capability in (
        "whatsapp.messaging",
        "whatsapp.webhook",
        "whatsapp.audio",
    ):
        op.execute(
            sa.text(
                f"""
                INSERT INTO assistant_integration_capabilities
                    (connection_id, capability)
                SELECT channel_id, '{capability}'
                FROM assistant_whatsapp_channels
                """
            )
        )

    op.execute(
        sa.text(
            """
            INSERT INTO assistant_integration_events
                (event_id, connection_id, tenant_id, unit_id, actor_id,
                 event_type, metadata_json, created_at)
            SELECT
                'migration-0004-' || channel_id,
                channel_id,
                tenant_id,
                unit_id,
                'migration:20261018_0004',
                'integration.migrated_from_whatsapp_v1',
                '{}',
                CURRENT_TIMESTAMP
            FROM assistant_whatsapp_channels
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_integration_event_scope",
        table_name="assistant_integration_events",
    )
    op.drop_index(
        "ix_assistant_integration_events_connection_id",
        table_name="assistant_integration_events",
    )
    op.drop_table("assistant_integration_events")

    op.drop_index(
        "ix_assistant_integration_validation_latest",
        table_name="assistant_integration_validations",
    )
    op.drop_index(
        "ix_assistant_integration_validations_connection_id",
        table_name="assistant_integration_validations",
    )
    op.drop_table("assistant_integration_validations")

    op.drop_table("assistant_integration_capabilities")

    op.drop_index(
        "ix_assistant_integration_inbound_status",
        table_name="assistant_integration_inbound",
    )
    op.drop_table("assistant_integration_inbound")

    op.drop_index(
        "ix_assistant_integration_secret_active",
        table_name="assistant_integration_secret_versions",
    )
    op.drop_table("assistant_integration_secret_versions")

    op.drop_index(
        "ix_assistant_integration_scope",
        table_name="assistant_integration_connections",
    )
    op.drop_index(
        "ix_assistant_integration_connections_provider_key",
        table_name="assistant_integration_connections",
    )
    op.drop_index(
        "ix_assistant_integration_connections_tenant_id",
        table_name="assistant_integration_connections",
    )
    op.drop_table("assistant_integration_connections")
    op.drop_table("assistant_integration_providers")
