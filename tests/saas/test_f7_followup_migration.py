"""F7 migration upgrade keeps CRM data and only adds scoped preferences."""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


def upgrade(url: str, target: str) -> None:
    env = dict(os.environ)
    env["FM_ASSISTANT_DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", target],
        cwd=os.getcwd(), env=env, capture_output=True,
        text=True, check=True,
    )


def test_f7_additive_migration_preserves_prior_crm(tmp_path):
    url = f"sqlite:///{tmp_path / 'followup.db'}"
    upgrade(url, "20261024_0026")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO assistant_crm_contacts "
            "(contact_id, tenant_id, unit_id, name, revision, created_at, updated_at) "
            "VALUES ('contact-existing','tenant-1','unit-1','Contato',1,"
            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
    upgrade(url, "head")
    assert "assistant_followup_preferences" in inspect(engine).get_table_names()
    with engine.connect() as conn:
        assert conn.scalar(text(
            "SELECT name FROM assistant_crm_contacts "
            "WHERE contact_id='contact-existing'"
        )) == "Contato"
        assert conn.scalar(text(
            "SELECT COUNT(*) FROM assistant_followup_preferences"
        )) == 0
    engine.dispose()
