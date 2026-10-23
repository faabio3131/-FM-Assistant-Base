"""VendeAtendeIA: fila de atendimento humano, sem gerar resposta por IA.

Operadores utilizam sessão humana e escopo tenant/unidade do login.
Atribuição e retorno para IA são transações determinísticas; a trilha de
eventos registra quem tomou a ação sem expor anotações privadas ao cliente.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from .db import (
    Base,
    ConversationORM,
    MembershipORM,
    MembershipUnitORM,
    MessageORM,
    UserORM,
)
from .identity import Permission, Role, permissions_for_role
from .identity_repository import SessionPrincipal


class HumanInboxStateORM(Base):
    __tablename__ = "assistant_human_inbox_state"

    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_conversations.conversation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_human_inbox_scope", "tenant_id", "unit_id", "assigned_to"),
    )


class HumanInboxEventORM(Base):
    __tablename__ = "assistant_human_inbox_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    private_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_human_inbox_event_scope", "tenant_id", "unit_id", "conversation_id",
              "created_at"),
    )


class HumanInboxDenied(RuntimeError):
    """Not found or non-authorized operation: never expose foreign ownership."""


class HumanInbox:
    def __init__(self, sessions: sessionmaker) -> None:
        self._sessions = sessions

    @staticmethod
    def _manager(principal: SessionPrincipal) -> bool:
        return principal.role in {Role.OWNER, Role.ADMIN, Role.MANAGER}

    @staticmethod
    def _view(conversation: ConversationORM, state: HumanInboxStateORM | None) -> dict:
        return {
            "conversation_id": conversation.conversation_id,
            "channel": conversation.channel,
            "status": conversation.status,
            "external_ref": conversation.external_ref,
            "assigned_to": state.assigned_to if state else None,
            "revision": state.revision if state else 0,
            "updated_at": conversation.updated_at.isoformat(),
        }

    def list_queue(
        self, *, principal: SessionPrincipal, page: int = 0,
        limit: int = 50,
    ) -> dict:
        if page < 0 or page > 20000 or not 1 <= limit <= 100:
            raise HumanInboxDenied("inbox.invalid_page")
        from .human_inbox_operations import HumanInboxOperations
        policy = HumanInboxOperations(self._sessions).policy(principal=principal)
        now = datetime.now(UTC)
        with self._sessions() as db:
            rows = db.execute(
                select(ConversationORM, HumanInboxStateORM)
                .outerjoin(
                    HumanInboxStateORM,
                    HumanInboxStateORM.conversation_id == ConversationORM.conversation_id,
                ).where(
                    ConversationORM.tenant_id == principal.tenant_id,
                    ConversationORM.unit_id == principal.unit_id,
                    ConversationORM.status == "human_handoff",
                ).order_by(
                    ConversationORM.updated_at.desc(), ConversationORM.conversation_id.desc(),
                ).offset(page * limit).limit(limit + 1)
            ).all()
            return {
                "items": [{
                    **self._view(conv, state),
                    "waiting_minutes": max(0, int((now - conv.updated_at.replace(
                        tzinfo=conv.updated_at.tzinfo or UTC
                    )).total_seconds() // 60)),
                    "sla_minutes": policy["first_response_minutes"],
                    "sla_overdue": (now - conv.updated_at.replace(
                        tzinfo=conv.updated_at.tzinfo or UTC
                    )).total_seconds() >= 60 * policy["first_response_minutes"],
                } for conv, state in rows[:limit]],
                "next_page": page + 1 if len(rows) > limit else None,
            }

    def _get_locked(self, db, principal: SessionPrincipal, conversation_id: str):
        conversation = db.scalar(
            select(ConversationORM).where(
                ConversationORM.conversation_id == conversation_id,
                ConversationORM.tenant_id == principal.tenant_id,
                ConversationORM.unit_id == principal.unit_id,
            ).with_for_update()
        )
        if conversation is None:
            raise HumanInboxDenied("inbox.not_found")
        state = db.scalar(select(HumanInboxStateORM).where(
            HumanInboxStateORM.conversation_id == conversation_id,
            HumanInboxStateORM.tenant_id == principal.tenant_id,
            HumanInboxStateORM.unit_id == principal.unit_id,
        ).with_for_update())
        return conversation, state

    @staticmethod
    def _event(db, *, principal: SessionPrincipal, conversation_id: str,
               action: str, assigned_to: str | None, note: str | None = None) -> None:
        db.add(HumanInboxEventORM(
            event_id=str(uuid4()), conversation_id=conversation_id,
            tenant_id=principal.tenant_id, unit_id=principal.unit_id,
            actor_id=principal.user_id, action=action, assigned_to=assigned_to,
            private_note=note, created_at=datetime.now(UTC),
        ))

    def _eligible_agent(self, db, principal: SessionPrincipal, target: str) -> None:
        membership = db.scalar(
            select(MembershipORM).join(UserORM, UserORM.user_id == MembershipORM.user_id)
            .join(MembershipUnitORM, MembershipUnitORM.membership_id == MembershipORM.membership_id)
            .where(
                MembershipORM.user_id == target,
                MembershipORM.tenant_id == principal.tenant_id,
                MembershipORM.active.is_(True),
                UserORM.active.is_(True),
                MembershipUnitORM.tenant_id == principal.tenant_id,
                MembershipUnitORM.unit_id == principal.unit_id,
            )
        )
        if membership is None or (
            Permission.CONVERSATION_RESPOND not in permissions_for_role(Role(membership.role))
        ):
            raise HumanInboxDenied("inbox.agent_not_eligible")

    def claim(self, *, principal: SessionPrincipal, conversation_id: str) -> dict:
        try:
            with self._sessions.begin() as db:
                conv, state = self._get_locked(db, principal, conversation_id)
                if conv.status != "human_handoff":
                    raise HumanInboxDenied("inbox.not_waiting")
                if state and state.assigned_to not in (None, principal.user_id):
                    raise HumanInboxDenied("inbox.already_assigned")
                if state and state.assigned_to == principal.user_id:
                    return self._view(conv, state)
                now = datetime.now(UTC)
                if state is None:
                    state = HumanInboxStateORM(
                        conversation_id=conversation_id, tenant_id=principal.tenant_id,
                        unit_id=principal.unit_id, assigned_to=principal.user_id,
                        revision=1, updated_at=now,
                    )
                    db.add(state)
                else:
                    state.assigned_to = principal.user_id
                    state.revision += 1
                    state.updated_at = now
                self._event(db, principal=principal, conversation_id=conversation_id,
                            action="claim", assigned_to=principal.user_id)
                return self._view(conv, state)
        except IntegrityError as exc:
            raise HumanInboxDenied("inbox.concurrent_claim") from exc

    def transfer(
        self, *, principal: SessionPrincipal, conversation_id: str,
        target_user_id: str,
    ) -> dict:
        if not target_user_id or len(target_user_id) > 64:
            raise HumanInboxDenied("inbox.invalid_target")
        with self._sessions.begin() as db:
            conv, state = self._get_locked(db, principal, conversation_id)
            if conv.status != "human_handoff" or state is None or (
                state.assigned_to != principal.user_id and not self._manager(principal)
            ):
                raise HumanInboxDenied("inbox.transfer_forbidden")
            self._eligible_agent(db, principal, target_user_id)
            if state.assigned_to != target_user_id:
                state.assigned_to = target_user_id
                state.revision += 1
                state.updated_at = datetime.now(UTC)
                self._event(db, principal=principal, conversation_id=conversation_id,
                            action="transfer", assigned_to=target_user_id)
            return self._view(conv, state)

    def add_note(
        self, *, principal: SessionPrincipal, conversation_id: str, note: str,
    ) -> dict:
        value = note.strip()
        if not 1 <= len(value) <= 4000:
            raise HumanInboxDenied("inbox.invalid_note")
        with self._sessions.begin() as db:
            conv, state = self._get_locked(db, principal, conversation_id)
            if conv.status != "human_handoff" or state is None or (
                state.assigned_to != principal.user_id and not self._manager(principal)
            ):
                raise HumanInboxDenied("inbox.note_forbidden")
            self._event(db, principal=principal, conversation_id=conversation_id,
                        action="note", assigned_to=state.assigned_to, note=value)
            return {"status": "saved", "conversation_id": conversation_id}

    def reply(
        self, *, principal: SessionPrincipal, conversation_id: str,
        message_id: str, content: str,
    ) -> dict:
        """Persist a human answer consumed by the existing WEBCHAT/API history.

        WhatsApp is deliberately excluded until its separate transactional
        outbound delivery intent and provider acknowledgement are connected.
        """
        value = content.strip()
        if not value or len(value) > 20_000:
            raise HumanInboxDenied("inbox.invalid_reply")
        try:
            with self._sessions.begin() as db:
                conv, state = self._get_locked(db, principal, conversation_id)
                if conv.status != "human_handoff" or state is None or (
                    state.assigned_to != principal.user_id and not self._manager(principal)
                ):
                    raise HumanInboxDenied("inbox.reply_forbidden")
                if conv.channel not in {"api", "webchat"}:
                    raise HumanInboxDenied("inbox.channel_delivery_not_connected")
                prior = db.get(MessageORM, message_id)
                if prior is not None:
                    if (prior.conversation_id != conversation_id or
                        prior.tenant_id != principal.tenant_id or
                        prior.unit_id != principal.unit_id or
                        prior.role != "assistant" or prior.content != value):
                        raise HumanInboxDenied("inbox.reply_idempotency_conflict")
                    return {"status": "already_recorded", "message_id": message_id}
                now = datetime.now(UTC)
                db.add(MessageORM(
                    message_id=message_id, conversation_id=conversation_id,
                    tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                    role="assistant", content=value, created_at=now,
                ))
                self._event(db, principal=principal, conversation_id=conversation_id,
                            action="human_reply", assigned_to=state.assigned_to)
                conv.updated_at = now
            return {"status": "stored_for_client", "message_id": message_id}
        except IntegrityError as exc:
            raise HumanInboxDenied("inbox.reply_concurrent_duplicate") from exc

    def return_to_ai(self, *, principal: SessionPrincipal, conversation_id: str) -> dict:
        with self._sessions.begin() as db:
            conv, state = self._get_locked(db, principal, conversation_id)
            if conv.status != "human_handoff" or state is None or (
                state.assigned_to != principal.user_id and not self._manager(principal)
            ):
                raise HumanInboxDenied("inbox.return_forbidden")
            if conv.channel == "whatsapp":
                from .human_whatsapp_outbox import HumanWhatsAppOutboxORM
                unsettled = db.scalar(select(HumanWhatsAppOutboxORM.message_id).where(
                    HumanWhatsAppOutboxORM.conversation_id == conversation_id,
                    HumanWhatsAppOutboxORM.tenant_id == principal.tenant_id,
                    HumanWhatsAppOutboxORM.unit_id == principal.unit_id,
                    HumanWhatsAppOutboxORM.state.in_(("pending", "sending_uncertain")),
                ).limit(1))
                if unsettled is not None:
                    raise HumanInboxDenied("inbox.outbound_pending_or_uncertain")
            affected = db.execute(update(ConversationORM).where(
                ConversationORM.conversation_id == conversation_id,
                ConversationORM.tenant_id == principal.tenant_id,
                ConversationORM.unit_id == principal.unit_id,
                ConversationORM.status == "human_handoff",
            ).values(status="open", updated_at=datetime.now(UTC))).rowcount
            if affected != 1:
                raise HumanInboxDenied("inbox.concurrent_state_change")
            self._event(db, principal=principal, conversation_id=conversation_id,
                        action="return_to_ai", assigned_to=None)
            state.assigned_to = None
            state.revision += 1
            state.updated_at = datetime.now(UTC)
            conv.status = "open"
            return self._view(conv, state)

    def activity(self, *, principal: SessionPrincipal, conversation_id: str,
                 page: int = 0, limit: int = 50) -> dict:
        if page < 0 or page > 20000 or not 1 <= limit <= 100:
            raise HumanInboxDenied("inbox.invalid_page")
        with self._sessions() as db:
            conv, _state = self._get_locked(db, principal, conversation_id)
            if conv is None:
                raise HumanInboxDenied("inbox.not_found")
            events = db.scalars(select(HumanInboxEventORM).where(
                HumanInboxEventORM.conversation_id == conversation_id,
                HumanInboxEventORM.tenant_id == principal.tenant_id,
                HumanInboxEventORM.unit_id == principal.unit_id,
            ).order_by(
                HumanInboxEventORM.created_at.desc(), HumanInboxEventORM.event_id.desc(),
            ).offset(page * limit).limit(limit + 1)).all()
            return {
                "items": [{
                    "event_id": e.event_id, "actor_id": e.actor_id,
                    "action": e.action, "assigned_to": e.assigned_to,
                    "private_note": e.private_note, "created_at": e.created_at.isoformat(),
                } for e in events[:limit]],
                "next_page": page + 1 if len(events) > limit else None,
            }
