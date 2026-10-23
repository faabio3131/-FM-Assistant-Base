"""F5 real-time operator presence and tenant/unit-specific SLA configuration."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, Integer, String, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, MembershipORM, MembershipUnitORM, UserORM
from .human_inbox import HumanInboxDenied
from .identity import Permission, Role, permissions_for_role
from .identity_repository import SessionPrincipal


class InboxSlaPolicyORM(Base):
    __tablename__ = "assistant_human_inbox_sla_policies"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    presence_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InboxAgentPresenceORM(Base):
    __tablename__ = "assistant_human_inbox_presence"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HumanInboxOperations:
    DEFAULT_RESPONSE_MINUTES = 20
    DEFAULT_PRESENCE_SECONDS = 120

    def __init__(self, sessions) -> None:
        self._sessions = sessions

    @staticmethod
    def _manager(principal: SessionPrincipal) -> None:
        if principal.role not in {Role.OWNER, Role.ADMIN, Role.MANAGER}:
            raise HumanInboxDenied("inbox.sla_manager_required")

    def policy(self, *, principal: SessionPrincipal) -> dict:
        with self._sessions() as db:
            row = db.get(InboxSlaPolicyORM, (principal.tenant_id, principal.unit_id))
            return {
                "first_response_minutes": (
                    row.first_response_minutes if row else self.DEFAULT_RESPONSE_MINUTES
                ),
                "presence_timeout_seconds": (
                    row.presence_timeout_seconds if row else self.DEFAULT_PRESENCE_SECONDS
                ),
                "revision": row.revision if row else 0,
                "tenant_id": principal.tenant_id,
                "unit_id": principal.unit_id,
            }

    def configure(
        self, *, principal: SessionPrincipal, first_response_minutes: int,
        presence_timeout_seconds: int, expected_revision: int,
    ) -> dict:
        self._manager(principal)
        if (
            type(first_response_minutes) is not int
            or not 1 <= first_response_minutes <= 1440
            or type(presence_timeout_seconds) is not int
            or not 30 <= presence_timeout_seconds <= 900
            or type(expected_revision) is not int
            or not 0 <= expected_revision < 1_000_000
        ):
            raise HumanInboxDenied("inbox.sla_policy_invalid")
        now = datetime.now(UTC)
        try:
            with self._sessions.begin() as db:
                row = db.get(InboxSlaPolicyORM, (principal.tenant_id, principal.unit_id))
                if row is None:
                    if expected_revision != 0:
                        raise HumanInboxDenied("inbox.sla_revision_conflict")
                    db.add(InboxSlaPolicyORM(
                        tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                        first_response_minutes=first_response_minutes,
                        presence_timeout_seconds=presence_timeout_seconds, revision=1,
                        updated_by=principal.user_id, updated_at=now,
                    ))
                else:
                    updated = db.execute(update(InboxSlaPolicyORM).where(
                        InboxSlaPolicyORM.tenant_id == principal.tenant_id,
                        InboxSlaPolicyORM.unit_id == principal.unit_id,
                        InboxSlaPolicyORM.revision == expected_revision,
                    ).values(
                        first_response_minutes=first_response_minutes,
                        presence_timeout_seconds=presence_timeout_seconds,
                        updated_by=principal.user_id, updated_at=now,
                        revision=expected_revision + 1,
                    )).rowcount
                    if updated != 1:
                        raise HumanInboxDenied("inbox.sla_revision_conflict")
        except IntegrityError as exc:
            raise HumanInboxDenied("inbox.sla_concurrent_update") from exc
        return self.policy(principal=principal)

    @staticmethod
    def _authorized(db, principal: SessionPrincipal) -> bool:
        return db.scalar(
            select(MembershipORM.membership_id).join(
                MembershipUnitORM,
                MembershipUnitORM.membership_id == MembershipORM.membership_id,
            ).join(UserORM, UserORM.user_id == MembershipORM.user_id).where(
                MembershipORM.tenant_id == principal.tenant_id,
                MembershipORM.user_id == principal.user_id,
                MembershipORM.active.is_(True), UserORM.active.is_(True),
                MembershipUnitORM.tenant_id == principal.tenant_id,
                MembershipUnitORM.unit_id == principal.unit_id,
            ).limit(1)
        ) is not None and Permission.CONVERSATION_RESPOND in permissions_for_role(principal.role)

    def heartbeat(self, *, principal: SessionPrincipal) -> dict:
        now = datetime.now(UTC)
        with self._sessions.begin() as db:
            if not self._authorized(db, principal):
                raise HumanInboxDenied("inbox.agent_not_eligible")
            row = db.get(InboxAgentPresenceORM, (
                principal.tenant_id, principal.unit_id, principal.user_id,
            ))
            if row is None:
                db.add(InboxAgentPresenceORM(
                    tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                    user_id=principal.user_id, last_seen=now,
                ))
            else:
                row.last_seen = now
        return {"status": "online", "last_seen": now.isoformat()}

    def online_agents(self, *, principal: SessionPrincipal) -> dict:
        with self._sessions() as db:
            policy = db.get(InboxSlaPolicyORM, (principal.tenant_id, principal.unit_id))
            timeout = (
                policy.presence_timeout_seconds if policy
                else self.DEFAULT_PRESENCE_SECONDS
            )
            cutoff = datetime.now(UTC) - timedelta(seconds=timeout)
            rows = db.execute(select(InboxAgentPresenceORM, UserORM, MembershipORM).join(
                UserORM, UserORM.user_id == InboxAgentPresenceORM.user_id,
            ).join(
                MembershipORM,
                (MembershipORM.user_id == InboxAgentPresenceORM.user_id)
                & (MembershipORM.tenant_id == InboxAgentPresenceORM.tenant_id),
            ).join(
                MembershipUnitORM,
                (MembershipUnitORM.membership_id == MembershipORM.membership_id)
                & (MembershipUnitORM.tenant_id == InboxAgentPresenceORM.tenant_id)
                & (MembershipUnitORM.unit_id == InboxAgentPresenceORM.unit_id),
            ).where(
                InboxAgentPresenceORM.tenant_id == principal.tenant_id,
                InboxAgentPresenceORM.unit_id == principal.unit_id,
                InboxAgentPresenceORM.last_seen >= cutoff,
                UserORM.active.is_(True), MembershipORM.active.is_(True),
            ).order_by(UserORM.display_name, UserORM.user_id).limit(100)).all()
            return {
                "items": [
                    {
                        "user_id": user.user_id, "display_name": user.display_name,
                        "last_seen": presence.last_seen.replace(
                            tzinfo=presence.last_seen.tzinfo or UTC
                        ).isoformat(),
                    }
                    for presence, user, membership in rows
                    if Permission.CONVERSATION_RESPOND in permissions_for_role(
                        Role(membership.role)
                    )
                ],
                "presence_timeout_seconds": timeout,
            }
