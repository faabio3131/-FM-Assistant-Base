"""Upgrade 0026 retains existing CRM contacts and opportunities in throwaway SQLite."""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


def upgrade(database_url: str, revision: str) -> None:
    env = os.environ.copy()
    env["FM_ASSISTANT_DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        check=True, cwd=os.getcwd(), env=env, capture_output=True, text=True,
    )


def test_additive_f6_workflow_migration_keeps_prior_crm_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'crm-v2.db'}"
    upgrade(url, "20261024_0025")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text(
            "INSERT INTO assistant_crm_contacts "
            "(contact_id,tenant_id,unit_id,name,revision,created_at,updated_at) "
            "VALUES ('contact-old','tenant-old','unit-old','Persistido',1,"
            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        db.execute(text(
            "INSERT INTO assistant_crm_opportunities "
            "(opportunity_id,tenant_id,unit_id,contact_id,title,amount_cents,"
            "stage,revision,created_at,updated_at) "
            "VALUES ('opp-old','tenant-old','unit-old','contact-old',"
            "'Negócio antigo',1234,'new',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
    upgrade(url, "head")
    with engine.connect() as db:
        names = set(inspect(db).get_table_names())
        assert {
            "assistant_crm_conversation_links", "assistant_crm_qualifications",
            "assistant_crm_proposals", "assistant_crm_activities",
        }.issubset(names)
        assert db.scalar(text("SELECT COUNT(*) FROM assistant_crm_activities")) == 0
        assert db.scalar(text(
            "SELECT amount_cents FROM assistant_crm_opportunities "
            "WHERE opportunity_id='opp-old'"
        )) == 1234
        assert db.scalar(text(
            "SELECT name FROM assistant_crm_contacts WHERE contact_id='contact-old'"
        )) == "Persistido"
    engine.dispose()
