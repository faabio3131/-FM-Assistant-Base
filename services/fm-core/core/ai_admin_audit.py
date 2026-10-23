"""F3.6.2: trilha append-only transacional para alterações administrativas governadas.

Não expõe endpoint de escrita. A tabela é criada por migration versionada,
não por create_all em runtime comercial.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from core.ai_command_authority import VerifiedCommandAdmin
from core.ai_control_plane import ControlPlaneBase


class CommandAdminAuditRecord(ControlPlaneBase):
    __tablename__ = "core_ai_admin_mutation_audit"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_jti: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("token_jti", name="uq_core_ai_admin_mutation_token_jti"),
    )


def stage_admin_mutation_audit(
    db: Session,
    *,
    principal: VerifiedCommandAdmin,
    action: str,
    resource_id: str,
    canonical_request: bytes,
    outcome: str = "committed",
) -> str:
    """Stage an audit entry in the SAME transaction as the authorized mutation.

    Caller owns commit/rollback. Unique jti means one delegated human assertion
    cannot authorize multiple writes. Never store raw request, prompt or secret.
    """
    if not action.strip() or not resource_id.strip():
        raise ValueError("admin_audit_scope_required")
    if len(action) > 128 or len(resource_id) > 256:
        raise ValueError("admin_audit_scope_too_long")
    if not canonical_request:
        raise ValueError("admin_audit_request_required")
    if outcome != "committed":
        raise ValueError("admin_audit_outcome_invalid")
    event_id = str(uuid4())
    db.add(
        CommandAdminAuditRecord(
            event_id=event_id,
            token_jti=principal.token_id,
            actor_user_id=principal.user_id,
            actor_session_id=principal.session_id,
            action=action,
            resource_id=resource_id,
            request_digest=sha256(canonical_request).hexdigest(),
            outcome=outcome,
            occurred_at=datetime.now(UTC),
        )
    )
    db.flush()
    return event_id
