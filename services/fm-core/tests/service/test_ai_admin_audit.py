from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from alembic import command
from core.ai_admin_audit import CommandAdminAuditRecord, stage_admin_mutation_audit
from core.ai_command_authority import VerifiedCommandAdmin
from core.ai_control_plane import AIProvider


def _principal(jti: str = "first-command-token-jti-1") -> VerifiedCommandAdmin:
    now = int(datetime.now(UTC).timestamp())
    return VerifiedCommandAdmin(
        user_id="platform-human-1",
        session_id="command-session-1",
        token_id=jti,
        issued_at=now,
        expires_at=now + 90,
        step_up_at=now,
        permissions=frozenset({"core.ai.admin.mutate"}),
    )


def _migrated(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    database_url = f"sqlite:///{tmp_path / 'f3-audit.db'}"
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    engine = create_engine(database_url)
    return engine, sessionmaker(engine, expire_on_commit=False)


def test_mutation_and_audit_share_transaction_and_reject_jti_replay(tmp_path):
    engine, sessions = _migrated(tmp_path)
    try:
        with sessions.begin() as db:
            db.add(AIProvider(
                provider_id="test-provider",
                adapter="openai_compatible",
                base_url="https://provider.invalid/v1",
                enabled=True,
            ))
        with sessions.begin() as db:
            provider = db.get(AIProvider, "test-provider")
            provider.enabled = False
            stage_admin_mutation_audit(
                db,
                principal=_principal(),
                action="core.ai.provider.disable",
                resource_id="test-provider",
                canonical_request=b'{"enabled":false,"provider":"test-provider"}',
            )
        with sessions() as db:
            audit = db.scalars(select(CommandAdminAuditRecord)).all()
            assert len(audit) == 1
            assert audit[0].actor_user_id == "platform-human-1"
            assert audit[0].actor_session_id == "command-session-1"
            assert audit[0].request_digest != 'SECRET-DO-NOT-STORE'
            assert len(audit[0].request_digest) == 64
            assert db.get(AIProvider, "test-provider").enabled is False

        with pytest.raises(IntegrityError), sessions.begin() as db:
            provider = db.get(AIProvider, "test-provider")
            provider.enabled = True
            stage_admin_mutation_audit(
                db,
                principal=_principal(),  # reused signed token jti
                action="core.ai.provider.enable",
                resource_id="test-provider",
                canonical_request=b'{"enabled":true}',
            )
        with sessions() as db:
            assert db.get(AIProvider, "test-provider").enabled is False
            assert len(db.scalars(select(CommandAdminAuditRecord)).all()) == 1
    finally:
        engine.dispose()


def test_rejected_or_rolled_back_mutation_leaves_no_audit(tmp_path):
    engine, sessions = _migrated(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="forced-rollback"), sessions.begin() as db:
            stage_admin_mutation_audit(
                db,
                principal=_principal("one-time-token-2"),
                action="core.ai.route.update",
                resource_id="policy-1",
                canonical_request=b"{}",
            )
            raise RuntimeError("forced-rollback")
        with sessions() as db:
            assert db.scalars(select(CommandAdminAuditRecord)).all() == []
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "action,resource,payload",
    [
        ("", "provider-a", b"{}"),
        ("core.ai.provider.disable", "", b"{}"),
        ("core.ai.provider.disable", "provider-a", b""),
    ],
)
def test_audit_requires_structured_scope(tmp_path, action, resource, payload):
    engine, sessions = _migrated(tmp_path)
    try:
        with pytest.raises(ValueError), sessions.begin() as db:
            stage_admin_mutation_audit(
                db,
                principal=_principal(),
                action=action,
                resource_id=resource,
                canonical_request=payload,
            )
    finally:
        engine.dispose()
