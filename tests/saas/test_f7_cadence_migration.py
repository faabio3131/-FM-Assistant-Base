"""F7 schema upgrade remains additive to customer CRM and contact policies."""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


def migrate(url: str, target: str) -> None:
    env = os.environ.copy()
    env["FM_ASSISTANT_DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", target],
        cwd=os.getcwd(), env=env, capture_output=True, text=True,
        check=True,
    )


def test_cadence_upgrade_preserves_existing_contacts_and_preferences(tmp_path):
    url = f"sqlite:///{tmp_path / 'cadence-v3.db'}"
    migrate(url, "20261024_0027")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO assistant_crm_contacts "
            "(contact_id,tenant_id,unit_id,name,revision,created_at,updated_at) "
            "VALUES ('existing','org','unit','Contato conservado',1,"
            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        conn.execute(text(
            "INSERT INTO assistant_followup_preferences "
            "(preference_id,tenant_id,unit_id,contact_id,channel,opted_out,timezone,"
            "quiet_start_minute,quiet_end_minute,revision,updated_by,updated_at) "
            "VALUES ('p1','org','unit','existing','whatsapp',1,'America/Sao_Paulo',"
            "1320,480,1,'owner',CURRENT_TIMESTAMP)"
        ))
    migrate(url, "head")
    assert {
        "assistant_cadence_definitions", "assistant_cadence_runs",
        "assistant_cadence_jobs", "assistant_cadence_events",
    }.issubset(set(inspect(engine).get_table_names()))
    with engine.connect() as conn:
        assert conn.scalar(text(
            "SELECT name FROM assistant_crm_contacts WHERE contact_id='existing'"
        )) == "Contato conservado"
        assert conn.scalar(text(
            "SELECT opted_out FROM assistant_followup_preferences WHERE preference_id='p1'"
        )) in (1, True)
        assert conn.scalar(text("SELECT COUNT(*) FROM assistant_cadence_jobs")) == 0
    engine.dispose()
