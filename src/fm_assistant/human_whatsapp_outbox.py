"""Human WhatsApp Evolution: encrypted inbound contact binding and one-shot outbox.

Never retry an ambiguous provider outcome automatically. A worker consumes a
durable outbox intent once and persists the Evolution HTTP acknowledgement.
The contact is not accepted from the browser; only authenticated inbound
transport may bind it to the conversation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, ConversationORM, IntegrationConnectionORM, MessageORM
from .human_inbox import HumanInboxDenied, HumanInboxEventORM, HumanInboxStateORM
from .identity import Role
from .identity_repository import SessionPrincipal


class HumanWhatsAppContactORM(Base):
    __tablename__ = "assistant_human_whatsapp_contacts"

    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_conversations.conversation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    connection_id: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_recipient: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HumanWhatsAppOutboxORM(Base):
    __tablename__ = "assistant_human_whatsapp_outbox"

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    connection_id: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_recipient: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_message: Mapped[str] = mapped_column(Text, nullable=False)
    message_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_to: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(160))
    operation_id: Mapped[str | None] = mapped_column(String(64))
    delivery_status: Mapped[str | None] = mapped_column(String(24))
    delivery_evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    delivery_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_reference: Mapped[str | None] = mapped_column(String(160))
    candidate_evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    candidate_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_human_whatsapp_queue", "state", "created_at"),
        Index("ix_human_whatsapp_scope", "tenant_id", "unit_id", "conversation_id"),
        Index("ix_human_whatsapp_provider_receipt", "connection_id", "provider_reference"),
    )


class HumanWhatsAppOutbox:
    def __init__(self, sessions, vault, *, sender_pepper: str) -> None:
        if not sender_pepper:
            raise ValueError("human_whatsapp_sender_pepper_required")
        self._sessions = sessions
        self._vault = vault
        self._pepper = sender_pepper.encode()

    def bind_verified_inbound(
        self, *, tenant_id: str, unit_id: str, conversation_id: str,
        connection_id: str, sender: str, external_ref: str,
    ) -> None:
        """Only called after the verified Evolution webhook selected the scope."""
        if not isinstance(sender, str) or not re.fullmatch(r"[0-9]{8,20}", sender):
            raise HumanInboxDenied("inbox.sender_invalid")
        digest = hmac.new(
            self._pepper, f"{connection_id}:{sender}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if external_ref != f"wae:{connection_id}:{digest}":
            raise HumanInboxDenied("inbox.sender_binding_mismatch")
        now = datetime.now(UTC)
        with self._sessions.begin() as db:
            conv = db.scalar(select(ConversationORM).where(
                ConversationORM.conversation_id == conversation_id,
                ConversationORM.tenant_id == tenant_id,
                ConversationORM.unit_id == unit_id,
                ConversationORM.channel == "whatsapp",
                ConversationORM.external_ref == external_ref,
            ).with_for_update())
            conn = db.scalar(select(IntegrationConnectionORM).where(
                IntegrationConnectionORM.connection_id == connection_id,
                IntegrationConnectionORM.tenant_id == tenant_id,
                IntegrationConnectionORM.unit_id == unit_id,
                IntegrationConnectionORM.provider_key == "whatsapp_evolution",
            ))
            if conv is None or conn is None:
                raise HumanInboxDenied("inbox.inbound_binding_denied")
            stored = db.get(HumanWhatsAppContactORM, conversation_id)
            if stored and stored.connection_id != connection_id:
                raise HumanInboxDenied("inbox.inbound_binding_conflict")
            encrypted = self._vault.encrypt(sender)
            if stored is None:
                db.add(HumanWhatsAppContactORM(
                    conversation_id=conversation_id, tenant_id=tenant_id,
                    unit_id=unit_id, connection_id=connection_id,
                    encrypted_recipient=encrypted, updated_at=now,
                ))
            else:
                stored.encrypted_recipient = encrypted
                stored.updated_at = now

    def enqueue(
        self, *, principal: SessionPrincipal, conversation_id: str,
        message_id: str, content: str,
    ) -> dict:
        value = content.strip()
        if not value or len(value) > 20_000:
            raise HumanInboxDenied("inbox.invalid_reply")
        if not isinstance(message_id, str) or len(message_id) != 36:
            raise HumanInboxDenied("inbox.invalid_message_id")
        digest = hashlib.sha256(value.encode()).hexdigest()
        now = datetime.now(UTC)
        try:
            with self._sessions.begin() as db:
                conv = db.scalar(select(ConversationORM).where(
                    ConversationORM.conversation_id == conversation_id,
                    ConversationORM.tenant_id == principal.tenant_id,
                    ConversationORM.unit_id == principal.unit_id,
                ).with_for_update())
                if conv is None or conv.channel != "whatsapp":
                    raise HumanInboxDenied("inbox.not_found")
                prior = db.get(HumanWhatsAppOutboxORM, message_id)
                if prior is not None:
                    if (
                        prior.tenant_id != principal.tenant_id
                        or prior.unit_id != principal.unit_id
                        or prior.conversation_id != conversation_id
                        or not hmac.compare_digest(prior.message_digest, digest)
                    ):
                        raise HumanInboxDenied("inbox.reply_idempotency_conflict")
                    return {"status": prior.state, "message_id": message_id}
                state = db.get(HumanInboxStateORM, conversation_id)
                if (
                    conv.status != "human_handoff" or state is None
                    or (state.assigned_to != principal.user_id and
                        principal.role not in {Role.OWNER, Role.ADMIN, Role.MANAGER})
                ):
                    raise HumanInboxDenied("inbox.reply_forbidden")
                contact = db.get(HumanWhatsAppContactORM, conversation_id)
                if contact is None:
                    raise HumanInboxDenied("inbox.contact_not_bound")
                conn = db.scalar(select(IntegrationConnectionORM).where(
                    IntegrationConnectionORM.connection_id == contact.connection_id,
                    IntegrationConnectionORM.tenant_id == principal.tenant_id,
                    IntegrationConnectionORM.unit_id == principal.unit_id,
                    IntegrationConnectionORM.provider_key == "whatsapp_evolution",
                    IntegrationConnectionORM.status == "active",
                ))
                if conn is None:
                    raise HumanInboxDenied("inbox.channel_unavailable")
                db.add(HumanWhatsAppOutboxORM(
                    message_id=message_id, conversation_id=conversation_id,
                    tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                    connection_id=contact.connection_id,
                    encrypted_recipient=contact.encrypted_recipient,
                    encrypted_message=self._vault.encrypt(value),
                    message_digest=digest, assigned_to=principal.user_id,
                    state="pending", provider_reference=None, operation_id=None,
                    created_at=now, updated_at=now,
                ))
                db.add(HumanInboxEventORM(
                    event_id=str(uuid4()), conversation_id=conversation_id,
                    tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                    actor_id=principal.user_id, action="whatsapp_queued",
                    assigned_to=state.assigned_to, private_note=None, created_at=now,
                ))
            return {"status": "pending", "message_id": message_id}
        except IntegrityError as exc:
            raise HumanInboxDenied("inbox.concurrent_enqueue") from exc

    def status(self, *, principal: SessionPrincipal, conversation_id: str,
               message_id: str) -> dict:
        with self._sessions() as db:
            row = db.get(HumanWhatsAppOutboxORM, message_id)
            if (row is None or row.tenant_id != principal.tenant_id
                or row.unit_id != principal.unit_id
                or row.conversation_id != conversation_id):
                raise HumanInboxDenied("inbox.not_found")
            return {
                "message_id": row.message_id, "status": row.state,
                "provider_reference": row.provider_reference,
                "delivery_status": row.delivery_status,
                "delivery_observed_at": (
                    row.delivery_observed_at.isoformat() if row.delivery_observed_at else None
                ),
                "provider_candidate": bool(row.candidate_evidence_sha256),
                "candidate_reference": row.candidate_reference,
                "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
                "automatic_resend": False,
            }

    def correlate_authenticated_status(
        self, *, connection_id: str, provider_reference: str,
        delivery_status: str, evidence_sha256: str,
    ) -> bool:
        """Only called after the established signed Evolution webhook verifier.

        A status receipt is not matched by phone, content, timestamp or operator
        input. It must match a unique provider ACK in this exact connection.
        """
        ranks = {"sent": 1, "delivered": 2, "read": 3}
        if (delivery_status not in ranks
            or not isinstance(connection_id, str)
            or not isinstance(provider_reference, str)
            or not 1 <= len(provider_reference) <= 160
            or not isinstance(evidence_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None):
            raise ValueError("inbox.delivery_evidence_invalid")
        with self._sessions.begin() as db:
            matches = db.scalars(select(HumanWhatsAppOutboxORM).where(
                HumanWhatsAppOutboxORM.connection_id == connection_id,
                HumanWhatsAppOutboxORM.provider_reference == provider_reference,
                HumanWhatsAppOutboxORM.state == "provider_acknowledged",
            ).with_for_update()).all()
            if len(matches) != 1:
                return False
            row = matches[0]
            if ranks[delivery_status] <= ranks.get(row.delivery_status, 0):
                return False
            row.delivery_status = delivery_status
            row.delivery_evidence_sha256 = evidence_sha256
            row.delivery_observed_at = datetime.now(UTC)
            row.updated_at = datetime.now(UTC)
            return True

    def review_queue(
        self, *, principal: SessionPrincipal, limit: int = 50,
    ) -> dict:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise HumanInboxDenied("inbox.review_limit_invalid")
        with self._sessions() as db:
            condition = [
                HumanWhatsAppOutboxORM.tenant_id == principal.tenant_id,
                HumanWhatsAppOutboxORM.unit_id == principal.unit_id,
                HumanWhatsAppOutboxORM.state.in_(("pending", "sending_uncertain")),
            ]
            if principal.role not in {Role.OWNER, Role.ADMIN, Role.MANAGER}:
                condition.append(HumanWhatsAppOutboxORM.assigned_to == principal.user_id)
            rows = db.scalars(select(HumanWhatsAppOutboxORM).where(
                *condition,
            ).order_by(
                HumanWhatsAppOutboxORM.created_at,
                HumanWhatsAppOutboxORM.message_id,
            ).limit(limit + 1)).all()
            return {
                "items": [{
                    "message_id": row.message_id,
                    "conversation_id": row.conversation_id,
                    "status": row.state,
                    "candidate_staged": row.candidate_evidence_sha256 is not None,
                    "reviewed": row.reviewed_at is not None,
                    "created_at": row.created_at.isoformat(),
                    "automatic_resend": False,
                } for row in rows[:limit]],
                "has_more": len(rows) > limit,
            }

    @staticmethod
    def _require_reviewer(principal: SessionPrincipal, row: HumanWhatsAppOutboxORM):
        if (row.tenant_id != principal.tenant_id
            or row.unit_id != principal.unit_id
            or (row.assigned_to != principal.user_id
                and principal.role not in {Role.OWNER, Role.ADMIN, Role.MANAGER})):
            raise HumanInboxDenied("inbox.review_forbidden")

    def investigate_uncertain(
        self, *, principal: SessionPrincipal, conversation_id: str,
        message_id: str, candidate_reference: str, integrations, transport,
    ) -> dict:
        """Provider readback is a candidate, never delivery proof or a resend."""
        if (not isinstance(candidate_reference, str)
            or re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", candidate_reference) is None):
            raise HumanInboxDenied("inbox.candidate_reference_invalid")
        with self._sessions() as db:
            row = db.get(HumanWhatsAppOutboxORM, message_id)
            if row is None or row.conversation_id != conversation_id:
                raise HumanInboxDenied("inbox.not_found")
            self._require_reviewer(principal, row)
            if row.state != "sending_uncertain":
                raise HumanInboxDenied("inbox.not_uncertain")
            connection_id = row.connection_id
            conn = db.scalar(select(IntegrationConnectionORM).where(
                IntegrationConnectionORM.connection_id == connection_id,
                IntegrationConnectionORM.tenant_id == principal.tenant_id,
                IntegrationConnectionORM.unit_id == principal.unit_id,
                IntegrationConnectionORM.provider_key == "whatsapp_evolution",
            ))
            if conn is None:
                raise HumanInboxDenied("inbox.channel_not_found")
            config = json.loads(conn.config_json)
            instance = config.get("instance_name")
            if not isinstance(instance, str) or not instance:
                raise HumanInboxDenied("inbox.instance_not_configured")
            if row.candidate_reference and row.candidate_reference != candidate_reference:
                raise HumanInboxDenied("inbox.candidate_conflict")
            other = db.scalar(select(HumanWhatsAppOutboxORM.message_id).where(
                HumanWhatsAppOutboxORM.connection_id == connection_id,
                HumanWhatsAppOutboxORM.provider_reference == candidate_reference,
                HumanWhatsAppOutboxORM.message_id != message_id,
            ).limit(1))
            if other is not None:
                raise HumanInboxDenied("inbox.candidate_already_claimed")
        secret = integrations.active_secret_ciphertexts(connection_id).get("instance_token")
        if secret is None:
            raise HumanInboxDenied("inbox.channel_unavailable")
        evidence_sha256 = transport.find_outbound_evidence(
            instance, instance_token=self._vault.decrypt(secret),
            provider_reference=candidate_reference,
        )
        if evidence_sha256 is None:
            return {"status": "not_found", "candidate_only": True, "automatic_resend": False}
        if (not isinstance(evidence_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None):
            raise HumanInboxDenied("inbox.candidate_invalid")
        with self._sessions.begin() as db:
            row = db.scalar(select(HumanWhatsAppOutboxORM).where(
                HumanWhatsAppOutboxORM.message_id == message_id,
                HumanWhatsAppOutboxORM.tenant_id == principal.tenant_id,
                HumanWhatsAppOutboxORM.unit_id == principal.unit_id,
                HumanWhatsAppOutboxORM.conversation_id == conversation_id,
            ).with_for_update())
            if row is None:
                raise HumanInboxDenied("inbox.not_found")
            self._require_reviewer(principal, row)
            if row.state != "sending_uncertain" or (
                row.candidate_reference and row.candidate_reference != candidate_reference
            ):
                raise HumanInboxDenied("inbox.candidate_conflict")
            row.candidate_reference = candidate_reference
            row.candidate_evidence_sha256 = evidence_sha256
            row.candidate_observed_at = datetime.now(UTC)
            row.updated_at = datetime.now(UTC)
            db.add(HumanInboxEventORM(
                event_id=str(uuid4()), conversation_id=conversation_id,
                tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                actor_id=principal.user_id, action="provider_candidate",
                assigned_to=row.assigned_to, private_note=None,
                created_at=datetime.now(UTC),
            ))
        return {"status": "candidate_only", "candidate_only": True,
                "automatic_resend": False}

    def review_uncertain(
        self, *, principal: SessionPrincipal, conversation_id: str,
        message_id: str, note: str,
    ) -> dict:
        if principal.role not in {Role.OWNER, Role.ADMIN, Role.MANAGER}:
            raise HumanInboxDenied("inbox.manager_required")
        note = note.strip()
        if not 10 <= len(note) <= 2000:
            raise HumanInboxDenied("inbox.review_note_invalid")
        with self._sessions.begin() as db:
            row = db.scalar(select(HumanWhatsAppOutboxORM).where(
                HumanWhatsAppOutboxORM.message_id == message_id,
                HumanWhatsAppOutboxORM.tenant_id == principal.tenant_id,
                HumanWhatsAppOutboxORM.unit_id == principal.unit_id,
                HumanWhatsAppOutboxORM.conversation_id == conversation_id,
            ).with_for_update())
            if row is None:
                raise HumanInboxDenied("inbox.not_found")
            if row.state != "sending_uncertain":
                raise HumanInboxDenied("inbox.not_uncertain")
            if row.reviewed_at is not None:
                return {"status": "reviewed_uncertain", "automatic_resend": False,
                        "delivery_confirmed": False}
            row.reviewed_by = principal.user_id
            row.reviewed_at = datetime.now(UTC)
            db.add(HumanInboxEventORM(
                event_id=str(uuid4()), conversation_id=conversation_id,
                tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                actor_id=principal.user_id, action="uncertain_reviewed",
                assigned_to=row.assigned_to, private_note=note,
                created_at=datetime.now(UTC),
            ))
        # Intent stays uncertain. No assertion of successful delivery, no resend.
        return {"status": "reviewed_uncertain", "automatic_resend": False,
                "delivery_confirmed": False}

    def process_one(self, *, integrations, transport) -> dict | None:
        """Trusted worker action, not a public HTTP route. At most one HTTP send."""
        with self._sessions.begin() as db:
            # PostgreSQL SKIP LOCKED avoids two workers claiming the same row.
            stmt = select(HumanWhatsAppOutboxORM).where(
                HumanWhatsAppOutboxORM.state == "pending",
            ).order_by(
                HumanWhatsAppOutboxORM.created_at,
                HumanWhatsAppOutboxORM.message_id,
            ).limit(1)
            if db.bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            item = db.scalar(stmt)
            if item is None:
                return None
            now = datetime.now(UTC)
            operation_id = str(uuid4())
            updated = db.execute(update(HumanWhatsAppOutboxORM).where(
                HumanWhatsAppOutboxORM.message_id == item.message_id,
                HumanWhatsAppOutboxORM.state == "pending",
            ).values(
                state="sending_uncertain", operation_id=operation_id, updated_at=now,
            )).rowcount
            if updated != 1:
                return None
            message_id = item.message_id
        # The durable, non-retryable send intent has committed.
        try:
            with self._sessions() as db:
                row = db.get(HumanWhatsAppOutboxORM, message_id)
                conv = db.get(ConversationORM, row.conversation_id)
                conn = db.scalar(select(IntegrationConnectionORM).where(
                    IntegrationConnectionORM.connection_id == row.connection_id,
                    IntegrationConnectionORM.tenant_id == row.tenant_id,
                    IntegrationConnectionORM.unit_id == row.unit_id,
                    IntegrationConnectionORM.provider_key == "whatsapp_evolution",
                ))
                if (
                    conv is None or conv.status != "human_handoff"
                    or conn is None or conn.status != "active"
                ):
                    # No send attempted, but quarantine conservatively.
                    return {"status": "sending_uncertain", "message_id": message_id}
                config = json.loads(conn.config_json)
                instance = config.get("instance_name")
                if not isinstance(instance, str) or not instance:
                    return {"status": "sending_uncertain", "message_id": message_id}
                recipient = self._vault.decrypt(row.encrypted_recipient)
                content = self._vault.decrypt(row.encrypted_message)
                ciphertext = integrations.active_secret_ciphertexts(row.connection_id).get(
                    "instance_token"
                )
                if ciphertext is None:
                    return {"status": "sending_uncertain", "message_id": message_id}
                token = self._vault.decrypt(ciphertext)
            # Serialize provider transmission against handoff return and
            # channel pause/revoke. Never hold the intent transaction over HTTP:
            # it was already committed above for crash-safe at-most-once send.
            with self._sessions.begin() as hold:
                locked_conv = hold.scalar(select(ConversationORM).where(
                    ConversationORM.conversation_id == row.conversation_id,
                    ConversationORM.tenant_id == row.tenant_id,
                    ConversationORM.unit_id == row.unit_id,
                ).with_for_update())
                locked_conn = hold.scalar(select(IntegrationConnectionORM).where(
                    IntegrationConnectionORM.connection_id == row.connection_id,
                    IntegrationConnectionORM.tenant_id == row.tenant_id,
                    IntegrationConnectionORM.unit_id == row.unit_id,
                ).with_for_update())
                if (locked_conv is None or locked_conv.status != "human_handoff"
                    or locked_conn is None or locked_conn.status != "active"
                    or locked_conn.revision != conn.revision):
                    return {"status": "sending_uncertain", "message_id": message_id}
                reference = transport.send_text(
                    instance, instance_token=token, recipient=recipient, message=content,
                )
            if not isinstance(reference, str) or not 1 <= len(reference) <= 160:
                raise RuntimeError("inbox.provider_reference_invalid")
            with self._sessions.begin() as db:
                updated = db.execute(update(HumanWhatsAppOutboxORM).where(
                    HumanWhatsAppOutboxORM.message_id == message_id,
                    HumanWhatsAppOutboxORM.state == "sending_uncertain",
                    HumanWhatsAppOutboxORM.operation_id == operation_id,
                ).values(
                    state="provider_acknowledged", provider_reference=reference,
                    updated_at=datetime.now(UTC),
                )).rowcount
                if updated != 1:
                    raise HumanInboxDenied("inbox.send_intent_lost")
                acknowledged_at = datetime.now(UTC)
                db.add(MessageORM(
                    message_id=message_id, conversation_id=row.conversation_id,
                    tenant_id=row.tenant_id, unit_id=row.unit_id,
                    role="assistant", content=content, created_at=acknowledged_at,
                ))
                db.execute(update(ConversationORM).where(
                    ConversationORM.conversation_id == row.conversation_id,
                    ConversationORM.tenant_id == row.tenant_id,
                    ConversationORM.unit_id == row.unit_id,
                ).values(updated_at=acknowledged_at))
            return {"status": "provider_acknowledged", "message_id": message_id}
        except Exception:  # noqa: BLE001 - uncertain provider outcome must never retry
            # No attempt to resend. Operator needs provider evidence.
            return {"status": "sending_uncertain", "message_id": message_id}
