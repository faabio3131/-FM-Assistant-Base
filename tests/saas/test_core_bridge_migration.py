"""F3.7.2: Alembic 0005 is additive and does not authorize identities."""

from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


def _upgrade(url: str, revision: str):
    env = os.environ.copy()
    env["FM_ASSISTANT_DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        check=True, cwd=os.getcwd(), env=env, capture_output=True, text=True,
    )


def test_bridge_migration_preserves_existing_integrations_and_has_no_active_identity(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration-bridge.db'}"
    _upgrade(url, "20261018_0004")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text(
            "INSERT INTO assistant_integration_providers "
            "(provider_key, integration_type, display_name, definition_version, "
            "enabled, created_at, updated_at) VALUES "
            "('test-ai', 'ai', 'Test', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    _upgrade(url, "head")
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261020_0017"
        # The new QR display projection is additive and never backfills
        # corporate authority or changes existing Core grants.
        assert db.scalar(text(
            "SELECT COUNT(*) FROM assistant_whatsapp_qr_display_policy"
        )) == 0
        assert db.scalar(text(
            "SELECT COUNT(*) FROM assistant_integration_providers "
            "WHERE provider_key='test-ai'"
        )) == 1
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_core_bridge_identities")) == 0
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_core_bridge_grants")) == 0
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_core_bridge_access")) == 0
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_command_bridge_control_events")) == 0
        assert db.scalar(text(
            "SELECT COUNT(*) FROM assistant_command_bridge_status_nonce"
        )) == 0
        indexes = inspect(db).get_indexes("assistant_command_bridge_control_events")
        assert any(
            index["name"] == "uq_assistant_command_bridge_control_request_id"
            and index["unique"]
            for index in indexes
        )
        names = set(inspect(db).get_table_names())
        assert {
            "assistant_core_bridge_identities",
            "assistant_core_bridge_grants",
            "assistant_core_bridge_access",
            "assistant_command_bridge_status_nonce",
            "assistant_plan_versions",
            "assistant_plan_limits",
            "assistant_plan_sync_nonces",
            "assistant_plan_binding_audit",
            "assistant_evolution_webhook_receipts",
            "assistant_evolution_inbound_jobs",
        }.issubset(names)
    engine.dispose()
