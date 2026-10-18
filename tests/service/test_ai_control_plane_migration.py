from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from core.ai_control_plane import ControlPlaneBase
import core.ai_usage_ledger  # noqa: F401 - registra metadata


def test_f3_versioned_migration_upgrade_downgrade(tmp_path):
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'migration.db'}")
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        command.upgrade(cfg, "head")
        assert set(ControlPlaneBase.metadata.tables) <= set(inspect(engine).get_table_names())
        assert "alembic_version" in inspect(engine).get_table_names()
        command.downgrade(cfg, "base")
        assert not (set(ControlPlaneBase.metadata.tables) & set(inspect(engine).get_table_names()))
        assert "core_ai_usage_events" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
