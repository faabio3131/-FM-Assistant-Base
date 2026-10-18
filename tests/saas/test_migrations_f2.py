from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, text


def _upgrade(database_url: str, revision: str) -> None:
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


def test_integration_migration_backfills_whatsapp_without_reencrypting(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration-f2.db'}"
    _upgrade(database_url, "20261017_0003")

    access_cipher = "cipher-access-existing"
    app_cipher = "cipher-app-existing"
    verify_cipher = "cipher-verify-existing"

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO assistant_whatsapp_channels
                    (channel_id, tenant_id, unit_id, phone_number_id,
                     business_account_id, access_token_ciphertext,
                     app_secret_ciphertext, verify_token_ciphertext,
                     graph_api_version, enabled, created_at, updated_at)
                VALUES
                    ('channel-existing', 'tenant-existing', 'unit-existing',
                     'phone-123', 'waba-123', :access_cipher, :app_cipher,
                     :verify_cipher, 'v23.0', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "access_cipher": access_cipher,
                "app_cipher": app_cipher,
                "verify_cipher": verify_cipher,
            },
        )

    _upgrade(database_url, "head")

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT connection_id, tenant_id, unit_id, provider_key, status, revision
                FROM assistant_integration_connections
                WHERE connection_id = 'channel-existing'
                """
            )
        ).one()
        secrets = dict(
            connection.execute(
                text(
                    """
                    SELECT secret_name, ciphertext
                    FROM assistant_integration_secret_versions
                    WHERE connection_id = 'channel-existing' AND active = 1
                    """
                )
            ).all()
        )
        capabilities = {
            item[0]
            for item in connection.execute(
                text(
                    """
                    SELECT capability
                    FROM assistant_integration_capabilities
                    WHERE connection_id = 'channel-existing'
                    """
                )
            ).all()
        }
        legacy_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM assistant_whatsapp_channels
                WHERE channel_id = 'channel-existing'
                """
            )
        ).scalar_one()

    assert row == (
        "channel-existing",
        "tenant-existing",
        "unit-existing",
        "whatsapp_meta",
        "active",
        1,
    )
    assert secrets == {
        "access_token": access_cipher,
        "app_secret": app_cipher,
        "verify_token": verify_cipher,
    }
    assert capabilities == {
        "whatsapp.messaging",
        "whatsapp.webhook",
        "whatsapp.audio",
    }
    assert legacy_count == 1
