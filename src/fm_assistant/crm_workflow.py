"""F6 CRM workflow: scoped conversation links, scoring, quotes and private activity.

All writes require a human principal with CRM_MANAGE, enforced by the HTTP layer.
Transactions verify *each* referenced resource in the same tenant and unit.
No automatic stage promotion, customer dispatch, or payment is performed.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .crm import CRMAuditORM, CRMConflict, CRMContactORM, CRMNotFound, CRMOpportunityORM
from .db import Base, ConversationORM
from .identity_repository import SessionPrincipal


class CRMConversationLinkORM(Base):
    __tablename__ = "assistant_crm_conversation_links"

    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_conversations.conversation_id"), primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_contacts.contact_id"), nullable=False,
    )
    opportunity_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("assistant_crm_opportunities.opportunity_id"),
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    linked_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_crm_links_contact_scope", "tenant_id", "unit_id", "contact_id"),
        Index("ix_crm_links_opportunity_scope", "tenant_id", "unit_id", "opportunity_id"),
    )


class CRMQualificationORM(Base):
    __tablename__ = "assistant_crm_qualifications"

    opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_opportunities.opportunity_id"),
        primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    need_confirmed: Mapped[bool] = mapped_column(nullable=False)
    budget_confirmed: Mapped[bool] = mapped_column(nullable=False)
    decision_maker_confirmed: Mapped[bool] = mapped_column(nullable=False)
    timeline_days: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CRMProposalORM(Base):
    __tablename__ = "assistant_crm_proposals"

    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_opportunities.opportunity_id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    terms_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_crm_proposals_scope", "tenant_id", "unit_id", "opportunity_id"),
    )


class CRMActivityORM(Base):
    __tablename__ = "assistant_crm_activities"

    activity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_opportunities.opportunity_id"),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    details_ciphertext: Mapped[str | None] = mapped_column(Text)
    related_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_crm_activities_scope", "tenant_id", "unit_id",
              "opportunity_id", "created_at"),
    )


def qualification_score(need: bool, budget: bool, decision: bool,
                        timeline_days: int | None) -> int:
    """Fixed explainable score. No AI judgment, probabilities or hidden weights."""
    if any(type(value) is not bool for value in (need, budget, decision)):
        raise CRMConflict("crm.qualification_invalid")
    if timeline_days is not None and (
        type(timeline_days) is not int or not 0 <= timeline_days <= 3650
    ):
        raise CRMConflict("crm.qualification_invalid")
    timeline_score = 15 if timeline_days is not None and timeline_days <= 30 else (
        8 if timeline_days is not None and timeline_days <= 90 else 0
    )
    return int(30 * need + 25 * budget + 30 * decision + timeline_score)


class CRMWorkflow:
    def __init__(self, sessions, vault) -> None:
        self._sessions = sessions
        self._vault = vault

    @staticmethod
    def _scope(db, principal: SessionPrincipal, opportunity_id: str):
        item = db.scalar(select(CRMOpportunityORM).where(
            CRMOpportunityORM.opportunity_id == opportunity_id,
            CRMOpportunityORM.tenant_id == principal.tenant_id,
            CRMOpportunityORM.unit_id == principal.unit_id,
        ).with_for_update())
        if item is None:
            raise CRMNotFound("crm.opportunity_not_found")
        return item

    @staticmethod
    def _audit(db, principal, kind, identifier, action):
        db.add(CRMAuditORM(
            event_id=str(uuid4()), tenant_id=principal.tenant_id,
            unit_id=principal.unit_id, actor_id=principal.user_id,
            entity_kind=kind, entity_id=identifier,
            action=action, created_at=datetime.now(UTC),
        ))

    @staticmethod
    def _activity(db, principal, opportunity_id, kind, ciphertext=None, related_id=None):
        db.add(CRMActivityORM(
            activity_id=str(uuid4()), tenant_id=principal.tenant_id,
            unit_id=principal.unit_id, opportunity_id=opportunity_id,
            actor_id=principal.user_id, kind=kind, details_ciphertext=ciphertext,
            related_id=related_id, created_at=datetime.now(UTC),
        ))

    @staticmethod
    def _link_view(row):
        return {
            "conversation_id": row.conversation_id, "contact_id": row.contact_id,
            "opportunity_id": row.opportunity_id, "revision": row.revision,
            "updated_at": row.updated_at.isoformat(),
        }

    def link_conversation(self, principal: SessionPrincipal, *,
                          conversation_id: str, contact_id: str,
                          opportunity_id: str | None, expected_revision: int) -> dict:
        if type(expected_revision) is not int or not 0 <= expected_revision <= 2_000_000_000:
            raise CRMConflict("crm.link_revision_invalid")
        try:
            with self._sessions.begin() as db:
                conversation = db.scalar(select(ConversationORM.conversation_id).where(
                    ConversationORM.conversation_id == conversation_id,
                    ConversationORM.tenant_id == principal.tenant_id,
                    ConversationORM.unit_id == principal.unit_id,
                ))
                contact = db.scalar(select(CRMContactORM.contact_id).where(
                    CRMContactORM.contact_id == contact_id,
                    CRMContactORM.tenant_id == principal.tenant_id,
                    CRMContactORM.unit_id == principal.unit_id,
                ))
                if not conversation or not contact:
                    raise CRMNotFound("crm.link_source_not_found")
                if opportunity_id is not None:
                    opp = self._scope(db, principal, opportunity_id)
                    if opp.contact_id != contact_id:
                        raise CRMConflict("crm.link_contact_mismatch")
                row = db.scalar(select(CRMConversationLinkORM).where(
                    CRMConversationLinkORM.conversation_id == conversation_id,
                    CRMConversationLinkORM.tenant_id == principal.tenant_id,
                    CRMConversationLinkORM.unit_id == principal.unit_id,
                ).with_for_update())
                now = datetime.now(UTC)
                if row is None:
                    if expected_revision != 0:
                        raise CRMConflict("crm.link_revision_conflict")
                    row = CRMConversationLinkORM(
                        conversation_id=conversation_id, tenant_id=principal.tenant_id,
                        unit_id=principal.unit_id, contact_id=contact_id,
                        opportunity_id=opportunity_id, revision=1,
                        linked_by=principal.user_id, updated_at=now,
                    )
                    db.add(row)
                else:
                    if row.revision != expected_revision:
                        raise CRMConflict("crm.link_revision_conflict")
                    changed = db.execute(update(CRMConversationLinkORM).where(
                        CRMConversationLinkORM.conversation_id == conversation_id,
                        CRMConversationLinkORM.tenant_id == principal.tenant_id,
                        CRMConversationLinkORM.unit_id == principal.unit_id,
                        CRMConversationLinkORM.revision == expected_revision,
                    ).values(
                        contact_id=contact_id, opportunity_id=opportunity_id,
                        revision=expected_revision + 1,
                        linked_by=principal.user_id, updated_at=now,
                    )).rowcount
                    if changed != 1:
                        raise CRMConflict("crm.link_revision_conflict")
                    db.refresh(row)
                self._audit(db, principal, "conversation", conversation_id, "linked")
                if opportunity_id:
                    self._activity(db, principal, opportunity_id, "conversation",
                                   related_id=conversation_id)
                return self._link_view(row)
        except IntegrityError as exc:
            raise CRMConflict("crm.link_concurrent_write") from exc

    def get_link(self, principal: SessionPrincipal, *, conversation_id: str) -> dict:
        with self._sessions() as db:
            row = db.scalar(select(CRMConversationLinkORM).where(
                CRMConversationLinkORM.conversation_id == conversation_id,
                CRMConversationLinkORM.tenant_id == principal.tenant_id,
                CRMConversationLinkORM.unit_id == principal.unit_id,
            ))
            if row is None:
                raise CRMNotFound("crm.link_not_found")
            return self._link_view(row)

    def links_for_opportunity(self, principal: SessionPrincipal, *,
                              opportunity_id: str) -> dict:
        with self._sessions() as db:
            self._scope(db, principal, opportunity_id)
            rows = db.scalars(select(CRMConversationLinkORM).where(
                CRMConversationLinkORM.tenant_id == principal.tenant_id,
                CRMConversationLinkORM.unit_id == principal.unit_id,
                CRMConversationLinkORM.opportunity_id == opportunity_id,
            ).order_by(CRMConversationLinkORM.updated_at.desc()).limit(100)).all()
            return {"items": [self._link_view(row) for row in rows]}

    @staticmethod
    def _qualification_view(row):
        return {
            "opportunity_id": row.opportunity_id,
            "need_confirmed": row.need_confirmed, "budget_confirmed": row.budget_confirmed,
            "decision_maker_confirmed": row.decision_maker_confirmed,
            "timeline_days": row.timeline_days, "score": row.score,
            "revision": row.revision, "updated_at": row.updated_at.isoformat(),
        }

    def qualify(self, principal: SessionPrincipal, *, opportunity_id: str,
                expected_revision: int, need: bool, budget: bool, decision: bool,
                timeline_days: int | None) -> dict:
        score = qualification_score(need, budget, decision, timeline_days)
        if type(expected_revision) is not int or not 0 <= expected_revision <= 2_000_000_000:
            raise CRMConflict("crm.qualification_revision_invalid")
        try:
            with self._sessions.begin() as db:
                opp = self._scope(db, principal, opportunity_id)
                if opp.stage in {"won", "lost"}:
                    raise CRMConflict("crm.qualification_terminal")
                row = db.scalar(select(CRMQualificationORM).where(
                    CRMQualificationORM.opportunity_id == opportunity_id,
                    CRMQualificationORM.tenant_id == principal.tenant_id,
                    CRMQualificationORM.unit_id == principal.unit_id,
                ).with_for_update())
                now = datetime.now(UTC)
                if row is None:
                    if expected_revision != 0:
                        raise CRMConflict("crm.qualification_revision_conflict")
                    row = CRMQualificationORM(
                        opportunity_id=opportunity_id, tenant_id=principal.tenant_id,
                        unit_id=principal.unit_id, need_confirmed=need,
                        budget_confirmed=budget, decision_maker_confirmed=decision,
                        timeline_days=timeline_days, score=score, revision=1,
                        updated_by=principal.user_id, updated_at=now,
                    )
                    db.add(row)
                else:
                    changed = db.execute(update(CRMQualificationORM).where(
                        CRMQualificationORM.opportunity_id == opportunity_id,
                        CRMQualificationORM.tenant_id == principal.tenant_id,
                        CRMQualificationORM.unit_id == principal.unit_id,
                        CRMQualificationORM.revision == expected_revision,
                    ).values(
                        need_confirmed=need, budget_confirmed=budget,
                        decision_maker_confirmed=decision, timeline_days=timeline_days,
                        score=score, revision=expected_revision + 1,
                        updated_by=principal.user_id, updated_at=now,
                    )).rowcount
                    if changed != 1:
                        raise CRMConflict("crm.qualification_revision_conflict")
                    db.refresh(row)
                self._audit(db, principal, "opportunity", opportunity_id, "qualified")
                self._activity(db, principal, opportunity_id, "qualification")
                return self._qualification_view(row)
        except IntegrityError as exc:
            raise CRMConflict("crm.qualification_concurrent_write") from exc

    def get_qualification(self, principal, *, opportunity_id: str) -> dict:
        with self._sessions() as db:
            self._scope(db, principal, opportunity_id)
            row = db.scalar(select(CRMQualificationORM).where(
                CRMQualificationORM.opportunity_id == opportunity_id,
                CRMQualificationORM.tenant_id == principal.tenant_id,
                CRMQualificationORM.unit_id == principal.unit_id,
            ))
            if row is None:
                raise CRMNotFound("crm.qualification_not_found")
            return self._qualification_view(row)

    def _proposal_view(self, row):
        return {
            "proposal_id": row.proposal_id, "opportunity_id": row.opportunity_id,
            "title": row.title, "terms": self._vault.decrypt(row.terms_ciphertext),
            "amount_cents": row.amount_cents, "status": row.status,
            "revision": row.revision, "created_at": row.created_at.isoformat(),
        }

    def create_proposal(self, principal, *, opportunity_id: str,
                        title: str, terms: str) -> dict:
        if (not isinstance(title, str) or not 1 <= len(title.strip()) <= 255
            or not isinstance(terms, str) or not 1 <= len(terms.strip()) <= 4000):
            raise CRMConflict("crm.proposal_invalid")
        with self._sessions.begin() as db:
            opp = self._scope(db, principal, opportunity_id)
            if opp.stage != "proposal":
                raise CRMConflict("crm.proposal_stage_required")
            now = datetime.now(UTC)
            row = CRMProposalORM(
                proposal_id=str(uuid4()), opportunity_id=opportunity_id,
                tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                title=title.strip(), terms_ciphertext=self._vault.encrypt(terms.strip()),
                amount_cents=opp.amount_cents, status="draft", revision=1,
                created_by=principal.user_id, created_at=now, updated_at=now,
            )
            db.add(row)
            self._audit(db, principal, "proposal", row.proposal_id, "created")
            self._activity(db, principal, opportunity_id, "proposal", related_id=row.proposal_id)
            return self._proposal_view(row)

    def list_proposals(self, principal, *, opportunity_id: str) -> dict:
        with self._sessions() as db:
            self._scope(db, principal, opportunity_id)
            rows = db.scalars(select(CRMProposalORM).where(
                CRMProposalORM.tenant_id == principal.tenant_id,
                CRMProposalORM.unit_id == principal.unit_id,
                CRMProposalORM.opportunity_id == opportunity_id,
            ).order_by(CRMProposalORM.created_at.desc(),
                       CRMProposalORM.proposal_id).limit(50)).all()
            return {"items": [self._proposal_view(r) for r in rows]}

    def change_proposal(self, principal, *, opportunity_id: str,
                        proposal_id: str, expected_revision: int, status: str) -> dict:
        if status not in {"ready", "withdrawn"} or (
            type(expected_revision) is not int or expected_revision < 1
        ):
            raise CRMConflict("crm.proposal_transition_invalid")
        with self._sessions.begin() as db:
            opp = self._scope(db, principal, opportunity_id)
            row = db.scalar(select(CRMProposalORM).where(
                CRMProposalORM.proposal_id == proposal_id,
                CRMProposalORM.opportunity_id == opportunity_id,
                CRMProposalORM.tenant_id == principal.tenant_id,
                CRMProposalORM.unit_id == principal.unit_id,
            ).with_for_update())
            if row is None:
                raise CRMNotFound("crm.proposal_not_found")
            if row.revision != expected_revision or (
                row.status != "draft" or status == "ready" and opp.stage != "proposal"
            ):
                raise CRMConflict("crm.proposal_transition_conflict")
            changed = db.execute(update(CRMProposalORM).where(
                CRMProposalORM.proposal_id == proposal_id,
                CRMProposalORM.tenant_id == principal.tenant_id,
                CRMProposalORM.unit_id == principal.unit_id,
                CRMProposalORM.revision == expected_revision,
                CRMProposalORM.status == "draft",
            ).values(status=status, revision=expected_revision + 1,
                     updated_at=datetime.now(UTC))).rowcount
            if changed != 1:
                raise CRMConflict("crm.proposal_transition_conflict")
            db.refresh(row)
            self._audit(db, principal, "proposal", proposal_id, status)
            self._activity(db, principal, opportunity_id,
                           "proposal_" + status, related_id=proposal_id)
            return self._proposal_view(row)

    def add_activity(self, principal, *, opportunity_id: str, kind: str,
                     details: str) -> dict:
        if kind not in {"note", "call", "meeting", "task"} or (
            not isinstance(details, str) or not 1 <= len(details.strip()) <= 4000
        ):
            raise CRMConflict("crm.activity_invalid")
        with self._sessions.begin() as db:
            self._scope(db, principal, opportunity_id)
            ciphertext = self._vault.encrypt(details.strip())
            self._activity(db, principal, opportunity_id, kind, ciphertext)
            self._audit(db, principal, "opportunity", opportunity_id, "activity")
            return {"status": "recorded"}

    def activities(self, principal, *, opportunity_id: str, page: int = 0) -> dict:
        if type(page) is not int or not 0 <= page <= 200:
            raise CRMConflict("crm.activity_page_invalid")
        with self._sessions() as db:
            self._scope(db, principal, opportunity_id)
            rows = db.scalars(select(CRMActivityORM).where(
                CRMActivityORM.tenant_id == principal.tenant_id,
                CRMActivityORM.unit_id == principal.unit_id,
                CRMActivityORM.opportunity_id == opportunity_id,
            ).order_by(CRMActivityORM.created_at.desc(),
                       CRMActivityORM.activity_id.desc())
                .offset(page * 50).limit(51)).all()
            return {
                "items": [{
                    "activity_id": row.activity_id,
                    "actor_id": row.actor_id, "kind": row.kind,
                    "details": self._vault.decrypt(row.details_ciphertext)
                    if row.details_ciphertext else None, "related_id": row.related_id,
                    "created_at": row.created_at.isoformat(),
                } for row in rows[:50]],
                "next_page": page + 1 if len(rows) > 50 else None,
            }
