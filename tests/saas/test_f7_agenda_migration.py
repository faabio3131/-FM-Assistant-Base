"""F7 agenda migration is reversible and additive to pre-existing CRM records."""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


def _run(url: str, *arguments: str) -> None:
    env = os.environ.copy()
    env["FM_ASSISTANT_DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=os.getcwd(), env=env, capture_output=True, text=True, check=True,
    )


def test_agenda_schema_upgrade_downgrade_preserves_crm(tmp_path):
    url = f"sqlite:///{tmp_path / 'agenda-migration.db'}"
    _run(url, "upgrade", "20261024_0028")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text(
            "INSERT INTO assistant_crm_contacts "
            "(contact_id, tenant_id, unit_id, name, revision, created_at, updated_at) "
            "VALUES ('c1','t1','u1','Conservado',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
    _run(url, "upgrade", "head")
    tables = set(inspect(engine).get_table_names())
    assert {"assistant_agenda_appointments", "assistant_agenda_events"} <= tables
    with engine.connect() as db:
        assert db.scalar(text(
            "SELECT name FROM assistant_crm_contacts WHERE contact_id='c1'"
        )) == "Conservado"
    _run(url, "downgrade", "20261024_0028")
    tables = set(inspect(engine).get_table_names())
    assert "assistant_agenda_appointments" not in tables
    assert "assistant_agenda_events" not in tables
    assert "assistant_crm_contacts" in tables
    engine.dispose()
