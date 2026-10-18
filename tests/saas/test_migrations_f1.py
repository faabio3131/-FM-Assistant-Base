from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, text


def _run_alembic(database_url: str, revision: str) -> None:
    env = os.environ.copy()
    env["FM_ASSISTANT_DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        check=True,
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )


def test_identity_migration_backfills_existing_tenant_and_unit(tmp_path):
    db_path = tmp_path / "migration-f1.db"
    database_url = f"sqlite:///{db_path}"

    _run_alembic(database_url, "20261003_0002")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO assistant_tenant_credentials
                    (credential_id, tenant_id, unit_id, key_hash, active, created_at)
                VALUES
                    ('cred-1', 'tenant-existing', 'unit-existing',
                     '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
                     1, CURRENT_TIMESTAMP)
                """
            )
        )

    _run_alembic(database_url, "head")

    with engine.connect() as connection:
        tenant = connection.execute(
            text(
                """
                SELECT tenant_id, status
                FROM assistant_tenants
                WHERE tenant_id = 'tenant-existing'
                """
            )
        ).one()
        unit = connection.execute(
            text(
                """
                SELECT tenant_id, unit_id, status
                FROM assistant_units
                WHERE tenant_id = 'tenant-existing' AND unit_id = 'unit-existing'
                """
            )
        ).one()
        license_row = connection.execute(
            text(
                """
                SELECT plan_code, status
                FROM assistant_tenant_licenses
                WHERE tenant_id = 'tenant-existing'
                """
            )
        ).one()

    assert tenant == ("tenant-existing", "active")
    assert unit == ("tenant-existing", "unit-existing", "active")
    assert license_row == ("legacy_foundation", "active")
