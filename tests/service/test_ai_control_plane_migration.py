from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

import core.ai_quota_store  # noqa: F401 - registra metadata
import core.ai_usage_ledger  # noqa: F401 - registra metadata
from alembic import command
from core.ai_control_plane import ControlPlaneBase


def test_f3_versioned_migration_upgrade_downgrade(tmp_path):
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'migration.db'}")
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        command.upgrade(cfg, "head")
        assert set(ControlPlaneBase.metadata.tables) <= set(inspect(engine).get_table_names())
        assert "alembic_version" in inspect(engine).get_table_names()
        assert "core_ai_quota_policies" in inspect(engine).get_table_names()
        assert "core_ai_quota_reservations" in inspect(engine).get_table_names()
        command.downgrade(cfg, "base")
        assert not (set(ControlPlaneBase.metadata.tables) & set(inspect(engine).get_table_names()))
        assert "core_ai_usage_events" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
