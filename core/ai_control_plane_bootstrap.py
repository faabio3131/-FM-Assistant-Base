"""Explicit F3.5 database-backed Core startup; never runs production migrations.

The database must already be migrated by a separately authorized process.
No tenant, secret or provider credentials are loaded into application globals.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import core.ai_admin_audit
from core.ai_control_plane import AIControlPlaneStore, ControlPlaneBase
from core.ai_control_plane_runtime import (
    CoreControlPlaneAIRuntime,
    CoreCredentialResolver,
    FMManagedCredentialResolver,
)
from core.ai_usage_ledger import PersistentAIFinOps
from core.seguranca.segredos import ReferenceSecretStore

REQUIRED_REVISION = "f3_0002"
REQUIRED_TABLES = frozenset(ControlPlaneBase.metadata.tables) | {
    "core_ai_price_snapshots",
    "core_ai_price_tariffs",
    "core_ai_usage_events",
}


def control_plane_is_ready(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            inspector = inspect(conn)
            if not REQUIRED_TABLES.issubset(inspector.get_table_names()):
                return False
            if "alembic_version" not in inspector.get_table_names():
                return False
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            return revision == [REQUIRED_REVISION]
    except SQLAlchemyError:
        return False


def build_persistent_core(
    database_url: str,
    *,
    credential_resolver: CoreCredentialResolver | None = None,
) -> tuple[CoreControlPlaneAIRuntime, Engine]:
    # The caller validates the URL and commercial environment before invoking.
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        if not control_plane_is_ready(engine):
            raise RuntimeError("core_control_plane_database_not_ready")
        sessions = sessionmaker(engine, expire_on_commit=False)
        runtime = CoreControlPlaneAIRuntime(
            control_plane=AIControlPlaneStore(sessions),
            credentials=credential_resolver or FMManagedCredentialResolver(
                ReferenceSecretStore()
            ),
            metering=PersistentAIFinOps(sessions),
        )
        return runtime, engine
    except BaseException:
        engine.dispose()
        raise
