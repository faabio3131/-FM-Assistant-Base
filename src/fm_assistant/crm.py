"""F6 CRM canonical sales data, scoped by authenticated tenant and unit.

Contact identifiers are never derived from browser scope. Email is encrypted
at rest and deduplicated by tenant-scoped HMAC; no email enters audit events.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .identity import normalize_email
from .identity_repository import SessionPrincipal


class CRMContactORM(Base):
    __tablename__ = "assistant_crm_contacts"

    contact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email_ciphertext: Mapped[str | None] = mapped_column(Text)
    email_fingerprint: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "unit_id", "email_fingerprint",
                         name="uq_crm_contact_email_scope"),
        Index("ix_crm_contacts_scope", "tenant_id", "unit_id", "created_at"),
    )


class CRMOpportunityORM(Base):
    __tablename__ = "assistant_crm_opportunities"

    opportunity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_contacts.contact_id"), nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_crm_opportunity_scope", "tenant_id", "unit_id", "stage", "created_at"),
    )


class CRMAuditORM(Base):
    __tablename__ = "assistant_crm_audit"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(24))
    to_stage: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CRMConflict(ValueError):
    pass


class CRMNotFound(ValueError):
    pass


_TRANSITIONS = {
    "new": frozenset(("qualified", "lost")),
    "qualified": frozenset(("proposal", "lost")),
    "proposal": frozenset(("won", "lost")),
    "won": frozenset(),
    "lost": frozenset(),
}


class CRMService:
    def __init__(self, sessions, vault, *, pepper: str) -> None:
        if not pepper:
            raise ValueError("crm_pepper_required")
        self._sessions = sessions
        self._vault = vault
        self._pepper = pepper.encode("utf-8")

    @staticmethod
    def _audit(db, principal: SessionPrincipal, kind: str, entity_id: str,
               action: str, old: str | None = None, new: str | None = None) -> None:
        db.add(CRMAuditORM(
            event_id=str(uuid4()), tenant_id=principal.tenant_id,
            unit_id=principal.unit_id, actor_id=principal.user_id,
            entity_kind=kind, entity_id=entity_id, action=action,
            from_stage=old, to_stage=new, created_at=datetime.now(UTC),
        ))

    def _fingerprint(self, principal: SessionPrincipal, email: str) -> str:
        return hmac.new(
            self._pepper,
            f"{principal.tenant_id}\0{principal.unit_id}\0{email}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def _contact_view(self, row: CRMContactORM) -> dict:
        return {
            "contact_id": row.contact_id, "name": row.name,
            "email": self._vault.decrypt(row.email_ciphertext)
            if row.email_ciphertext else None,
            "revision": row.revision, "created_at": row.created_at.isoformat(),
        }

    @staticmethod
    def _opportunity_view(row: CRMOpportunityORM) -> dict:
        return {
            "opportunity_id": row.opportunity_id, "contact_id": row.contact_id,
            "title": row.title, "amount_cents": row.amount_cents, "stage": row.stage,
            "revision": row.revision, "updated_at": row.updated_at.isoformat(),
        }

    def create_contact(self, principal: SessionPrincipal, *, name: str,
                       email: str | None) -> dict:
        name = name.strip()
        if not 1 <= len(name) <= 255:
            raise CRMConflict("crm.contact_name_invalid")
        if email is not None:
            try:
                email = normalize_email(email)
            except (ValueError, AttributeError) as exc:
                raise CRMConflict("crm.email_invalid") from exc
        now = datetime.now(UTC)
        row = CRMContactORM(
            contact_id=str(uuid4()), tenant_id=principal.tenant_id,
            unit_id=principal.unit_id, name=name,
            email_ciphertext=self._vault.encrypt(email) if email else None,
            email_fingerprint=self._fingerprint(principal, email) if email else None,
            revision=1, created_at=now, updated_at=now,
        )
        try:
            with self._sessions.begin() as db:
                db.add(row)
                self._audit(db, principal, "contact", row.contact_id, "created")
        except IntegrityError as exc:
            raise CRMConflict("crm.contact_already_exists") from exc
        return self._contact_view(row)

    def list_contacts(self, principal: SessionPrincipal, *, page: int = 0) -> dict:
        if type(page) is not int or not 0 <= page <= 200:
            raise CRMConflict("crm.invalid_page")
        with self._sessions() as db:
            rows = db.scalars(select(CRMContactORM).where(
                CRMContactORM.tenant_id == principal.tenant_id,
                CRMContactORM.unit_id == principal.unit_id,
            ).order_by(CRMContactORM.created_at.desc(), CRMContactORM.contact_id)
                .offset(page * 50).limit(51)).all()
            return {"items": [self._contact_view(row) for row in rows[:50]],
                    "next_page": page + 1 if len(rows) > 50 else None}

    def create_opportunity(self, principal: SessionPrincipal, *, contact_id: str,
                           title: str, amount_cents: int) -> dict:
        if not 1 <= len(title.strip()) <= 255 or type(amount_cents) is not int or (
            not 0 <= amount_cents <= 2_000_000_000
        ):
            raise CRMConflict("crm.opportunity_invalid")
        now = datetime.now(UTC)
        with self._sessions.begin() as db:
            contact = db.scalar(select(CRMContactORM.contact_id).where(
                CRMContactORM.contact_id == contact_id,
                CRMContactORM.tenant_id == principal.tenant_id,
                CRMContactORM.unit_id == principal.unit_id,
            ))
            if contact is None:
                raise CRMNotFound("crm.contact_not_found")
            row = CRMOpportunityORM(
                opportunity_id=str(uuid4()), tenant_id=principal.tenant_id,
                unit_id=principal.unit_id, contact_id=contact_id,
                title=title.strip(), amount_cents=amount_cents, stage="new",
                revision=1, created_at=now, updated_at=now,
            )
            db.add(row)
            self._audit(db, principal, "opportunity", row.opportunity_id,
                        "created", new="new")
        return self._opportunity_view(row)

    def list_opportunities(self, principal: SessionPrincipal, *, page: int = 0,
                           stage: str | None = None) -> dict:
        if type(page) is not int or not 0 <= page <= 200 or (
            stage is not None and stage not in _TRANSITIONS
        ):
            raise CRMConflict("crm.list_invalid")
        with self._sessions() as db:
            query = select(CRMOpportunityORM).where(
                CRMOpportunityORM.tenant_id == principal.tenant_id,
                CRMOpportunityORM.unit_id == principal.unit_id,
            )
            if stage:
                query = query.where(CRMOpportunityORM.stage == stage)
            rows = db.scalars(query.order_by(
                CRMOpportunityORM.created_at.desc(), CRMOpportunityORM.opportunity_id,
            ).offset(page * 50).limit(51)).all()
            return {"items": [self._opportunity_view(row) for row in rows[:50]],
                    "next_page": page + 1 if len(rows) > 50 else None}

    def analytics(self, principal: SessionPrincipal) -> dict:
        """Exact unit-scoped opportunity snapshot, not recognized revenue.

        A single grouped read covers every opportunity, not just the 50
        records currently loaded into the CRM workspace.
        """
        with self._sessions() as db:
            contacts = db.scalar(select(func.count(CRMContactORM.contact_id)).where(
                CRMContactORM.tenant_id == principal.tenant_id,
                CRMContactORM.unit_id == principal.unit_id,
            ))
            rows = db.execute(select(
                CRMOpportunityORM.stage,
                func.count(CRMOpportunityORM.opportunity_id),
                func.coalesce(func.sum(CRMOpportunityORM.amount_cents), 0),
            ).where(
                CRMOpportunityORM.tenant_id == principal.tenant_id,
                CRMOpportunityORM.unit_id == principal.unit_id,
            ).group_by(CRMOpportunityORM.stage)).all()
        stages = {
            stage: {"count": 0, "amount_cents": 0}
            for stage in _TRANSITIONS
        }
        for stage, count, amount in rows:
            if stage not in stages:
                raise CRMConflict("crm.analytics_unknown_stage")
            stages[stage] = {"count": int(count), "amount_cents": int(amount)}
        total = sum(row["count"] for row in stages.values())
        open_stages = ("new", "qualified", "proposal")
        closed = stages["won"]["count"] + stages["lost"]["count"]
        return {
            "currency": "BRL", "contacts_total": int(contacts or 0),
            "opportunities_total": total,
            "open_opportunities": sum(stages[k]["count"] for k in open_stages),
            "open_pipeline_cents": sum(stages[k]["amount_cents"] for k in open_stages),
            "won_opportunities": stages["won"]["count"],
            "won_opportunity_value_cents": stages["won"]["amount_cents"],
            "lost_opportunities": stages["lost"]["count"],
            "closed_opportunities": closed,
            "win_rate_basis_points": (stages["won"]["count"] * 10_000 // closed)
            if closed else None,
            "revenue_recognized": False,
            "stages": stages,
        }

    def advance(self, principal: SessionPrincipal, *, opportunity_id: str,
                expected_revision: int, stage: str,
                outcome_reason: str | None = None) -> dict:
        if stage not in _TRANSITIONS or type(expected_revision) is not int:
            raise CRMConflict("crm.transition_invalid")
        if outcome_reason is not None and (
            stage not in {"won", "lost"}
            or type(outcome_reason) is not str
            or not 1 <= len(outcome_reason.strip()) <= 500
        ):
            raise CRMConflict("crm.outcome_reason_invalid")
        with self._sessions.begin() as db:
            row = db.scalar(select(CRMOpportunityORM).where(
                CRMOpportunityORM.opportunity_id == opportunity_id,
                CRMOpportunityORM.tenant_id == principal.tenant_id,
                CRMOpportunityORM.unit_id == principal.unit_id,
            ).with_for_update())
            if row is None:
                raise CRMNotFound("crm.opportunity_not_found")
            if row.revision != expected_revision or (
                stage not in _TRANSITIONS[row.stage]
            ):
                raise CRMConflict("crm.transition_conflict")
            previous = row.stage
            now = datetime.now(UTC)
            changed = db.execute(update(CRMOpportunityORM).where(
                CRMOpportunityORM.opportunity_id == opportunity_id,
                CRMOpportunityORM.tenant_id == principal.tenant_id,
                CRMOpportunityORM.unit_id == principal.unit_id,
                CRMOpportunityORM.revision == expected_revision,
                CRMOpportunityORM.stage == previous,
            ).values(stage=stage, revision=expected_revision + 1,
                     updated_at=now)).rowcount
            if changed != 1:
                raise CRMConflict("crm.transition_conflict")
            self._audit(db, principal, "opportunity", opportunity_id, "transition",
                        old=previous, new=stage)
            if outcome_reason is not None:
                # One transaction: stale CAS cannot leave a standalone reason.
                # Keep sensitive commercial details encrypted like other CRM notes.
                from .crm_workflow import CRMActivityORM
                db.add(CRMActivityORM(
                    activity_id=str(uuid4()), tenant_id=principal.tenant_id,
                    unit_id=principal.unit_id, opportunity_id=opportunity_id,
                    actor_id=principal.user_id, kind="outcome_" + stage,
                    details_ciphertext=self._vault.encrypt(outcome_reason.strip()),
                    related_id=None, created_at=now,
                ))
            # Keep SQLAlchemy identity map in sync after the CAS update.
            db.refresh(row)
            return self._opportunity_view(row)
