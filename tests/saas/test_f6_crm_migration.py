"""F6 additive migration preserves existing records in disposable database."""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


def _upgrade(url: str, revision: str) -> None:
    env = os.environ.copy()
    env["FM_ASSISTANT_DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=os.getcwd(), check=True, env=env, capture_output=True, text=True,
    )


def test_crm_migration_is_additive_and_preserves_existing_tenant(tmp_path):
    url = f"sqlite:///{tmp_path / 'f6-migration.db'}"
    _upgrade(url, "20261023_0024")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text(
            "INSERT INTO assistant_tenants "
            "(tenant_id, display_name, slug, status, created_at, updated_at) "
            "VALUES ('old-tenant', 'Empresa antiga', 'old-tenant', 'active', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    _upgrade(url, "head")
    with engine.connect() as db:
        names = set(inspect(db).get_table_names())
        assert {
            "assistant_crm_contacts", "assistant_crm_opportunities",
            "assistant_crm_audit",
        }.issubset(names)
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_crm_contacts")) == 0
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_crm_opportunities")) == 0
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_crm_audit")) == 0
        assert db.scalar(text(
            "SELECT COUNT(*) FROM assistant_tenants WHERE tenant_id='old-tenant'"
        )) == 1
    engine.dispose()
