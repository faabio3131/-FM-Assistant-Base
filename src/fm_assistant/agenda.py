"""F7 private agenda: scoped appointments, conflict-free slots and internal reminders.

No calendar provider, WhatsApp, email or customer-facing dispatch is invoked.
PostgreSQL unit-row serialization protects cross-opportunity booking conflicts.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .crm import CRMConflict, CRMContactORM, CRMNotFound, CRMOpportunityORM
from .crm_workflow import CRMActivityORM
from .db import Base, UnitORM
from .identity_repository import SessionPrincipal


class AgendaAppointmentORM(Base):
    __tablename__ = "assistant_agenda_appointments"

    appointment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_contacts.contact_id"), nullable=False,
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_opportunities.opportunity_id"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remind_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "unit_id", "idempotency_key",
            name="uq_agenda_appointment_idempotency",
        ),
        Index(
            "ix_agenda_owner_range", "tenant_id", "unit_id",
            "owner_user_id", "status", "starts_at", "ends_at",
        ),
        Index("ix_agenda_reminders", "status", "remind_at"),
    )


class AgendaEventORM(Base):
    __tablename__ = "assistant_agenda_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    appointment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_agenda_appointments.appointment_id"),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index(
            "ix_agenda_events_scope", "tenant_id", "unit_id",
            "appointment_id", "created_at",
        ),
    )


def _instant(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CRMConflict("agenda.datetime_requires_timezone")
    return value.astimezone(UTC)


def _utc_from_db(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AgendaEngine:
    def __init__(self, sessions, vault) -> None:
        self._sessions = sessions
        self._vault = vault

    @staticmethod
    def _event(db, item: AgendaAppointmentORM, action: str, actor: str,
               when: datetime) -> None:
        db.add(AgendaEventORM(
            event_id=str(uuid4()), tenant_id=item.tenant_id, unit_id=item.unit_id,
            appointment_id=item.appointment_id, action=action, actor_id=actor,
            created_at=when,
        ))

    @staticmethod
    def _locked_unit(db, principal: SessionPrincipal) -> None:
        # Serializes all agenda mutations for this tenant/unit in PostgreSQL.
        row = db.scalar(select(UnitORM.unit_id).where(
            UnitORM.tenant_id == principal.tenant_id,
            UnitORM.unit_id == principal.unit_id,
        ).with_for_update())
        if row is None:
            raise CRMNotFound("agenda.unit_not_found")

    @staticmethod
    def _opportunity(db, principal: SessionPrincipal, contact_id: str,
                     opportunity_id: str) -> None:
        contact = db.scalar(select(CRMContactORM.contact_id).where(
            CRMContactORM.tenant_id == principal.tenant_id,
            CRMContactORM.unit_id == principal.unit_id,
            CRMContactORM.contact_id == contact_id,
        ))
        opp = db.scalar(select(CRMOpportunityORM).where(
            CRMOpportunityORM.opportunity_id == opportunity_id,
            CRMOpportunityORM.contact_id == contact_id,
            CRMOpportunityORM.tenant_id == principal.tenant_id,
            CRMOpportunityORM.unit_id == principal.unit_id,
        ))
        if contact is None or opp is None:
            raise CRMNotFound("agenda.contact_opportunity_not_found")
        if opp.stage in {"won", "lost"}:
            raise CRMConflict("agenda.opportunity_closed")

    @staticmethod
    def _scoped(db, principal: SessionPrincipal, appointment_id: str):
        row = db.scalar(select(AgendaAppointmentORM).where(
            AgendaAppointmentORM.appointment_id == appointment_id,
            AgendaAppointmentORM.tenant_id == principal.tenant_id,
            AgendaAppointmentORM.unit_id == principal.unit_id,
            AgendaAppointmentORM.owner_user_id == principal.user_id,
        ).with_for_update())
        if row is None:
            raise CRMNotFound("agenda.appointment_not_found")
        return row

    @staticmethod
    def _busy(db, principal: SessionPrincipal, start: datetime,
              end: datetime, exclude: str | None = None) -> bool:
        query = select(AgendaAppointmentORM.appointment_id).where(
            AgendaAppointmentORM.tenant_id == principal.tenant_id,
            AgendaAppointmentORM.unit_id == principal.unit_id,
            AgendaAppointmentORM.owner_user_id == principal.user_id,
            AgendaAppointmentORM.status == "scheduled",
            AgendaAppointmentORM.starts_at < end,
            AgendaAppointmentORM.ends_at > start,
        )
        if exclude:
            query = query.where(AgendaAppointmentORM.appointment_id != exclude)
        return db.scalar(query.limit(1)) is not None

    @staticmethod
    def _bounds(starts_at: datetime, duration_minutes: int,
                now: datetime | None = None) -> tuple[datetime, datetime]:
        start = _instant(starts_at)
        instant = _instant(now or datetime.now(UTC))
        if (type(duration_minutes) is not int or not 15 <= duration_minutes <= 480
            or start < instant - timedelta(minutes=5)
            or start > instant + timedelta(days=365)):
            raise CRMConflict("agenda.schedule_invalid")
        return start, start + timedelta(minutes=duration_minutes)

    def _view(self, item: AgendaAppointmentORM) -> dict:
        return {
            "appointment_id": item.appointment_id, "contact_id": item.contact_id,
            "opportunity_id": item.opportunity_id,
            "title": self._vault.decrypt(item.title_ciphertext),
            "starts_at": _utc_from_db(item.starts_at).isoformat(),
            "ends_at": _utc_from_db(item.ends_at).isoformat(),
            "remind_minutes": item.remind_minutes, "status": item.status,
            "revision": item.revision,
        }

    def create(self, principal: SessionPrincipal, *, contact_id: str,
               opportunity_id: str, title: str, starts_at: datetime,
               duration_minutes: int, remind_minutes: int,
               idempotency_key: str) -> dict:
        start = _instant(starts_at)
        if (type(title) is not str or not 1 <= len(title.strip()) <= 200
            or type(idempotency_key) is not str
            or not 8 <= len(idempotency_key) <= 128
            or type(remind_minutes) is not int or not 0 <= remind_minutes <= 10080
            or type(duration_minutes) is not int
            or not 15 <= duration_minutes <= 480):
            raise CRMConflict("agenda.payload_invalid")
        end = start + timedelta(minutes=duration_minutes)
        instant = datetime.now(UTC)
        try:
            with self._sessions.begin() as db:
                self._locked_unit(db, principal)
                existing = db.scalar(select(AgendaAppointmentORM).where(
                    AgendaAppointmentORM.tenant_id == principal.tenant_id,
                    AgendaAppointmentORM.unit_id == principal.unit_id,
                    AgendaAppointmentORM.idempotency_key == idempotency_key,
                ))
                if existing is not None:
                    if (existing.owner_user_id != principal.user_id
                        or existing.contact_id != contact_id
                        or existing.opportunity_id != opportunity_id
                        or self._vault.decrypt(existing.title_ciphertext) != title.strip()
                        or _utc_from_db(existing.starts_at) != start
                        or _utc_from_db(existing.ends_at) != end
                        or existing.remind_minutes != remind_minutes):
                        raise CRMConflict("agenda.idempotency_mismatch")
                    return self._view(existing)
                self._bounds(start, duration_minutes, now=instant)
                self._opportunity(db, principal, contact_id, opportunity_id)
                if self._busy(db, principal, start, end):
                    raise CRMConflict("agenda.slot_occupied")
                item = AgendaAppointmentORM(
                    appointment_id=str(uuid4()), tenant_id=principal.tenant_id,
                    unit_id=principal.unit_id, owner_user_id=principal.user_id,
                    contact_id=contact_id, opportunity_id=opportunity_id,
                    idempotency_key=idempotency_key,
                    title_ciphertext=self._vault.encrypt(title.strip()),
                    starts_at=start, ends_at=end,
                    remind_minutes=remind_minutes,
                    remind_at=start - timedelta(minutes=remind_minutes)
                    if remind_minutes else None,
                    reminder_revision=0, status="scheduled", revision=1,
                    created_by=principal.user_id, updated_by=principal.user_id,
                    created_at=instant, updated_at=instant,
                )
                db.add(item)
                self._event(db, item, "scheduled", principal.user_id, instant)
                db.flush()
                return self._view(item)
        except IntegrityError as exc:
            raise CRMConflict("agenda.concurrent_schedule") from exc

    def list(self, principal: SessionPrincipal, *, start_at: datetime,
             end_at: datetime) -> dict:
        start, end = _instant(start_at), _instant(end_at)
        if end <= start or end - start > timedelta(days=90):
            raise CRMConflict("agenda.range_invalid")
        with self._sessions() as db:
            rows = db.scalars(select(AgendaAppointmentORM).where(
                AgendaAppointmentORM.tenant_id == principal.tenant_id,
                AgendaAppointmentORM.unit_id == principal.unit_id,
                AgendaAppointmentORM.owner_user_id == principal.user_id,
                AgendaAppointmentORM.starts_at < end,
                AgendaAppointmentORM.ends_at > start,
            ).order_by(AgendaAppointmentORM.starts_at,
                       AgendaAppointmentORM.appointment_id).limit(101)).all()
            return {"items": [self._view(item) for item in rows[:100]],
                    "has_more": len(rows) > 100}

    def slots(self, principal: SessionPrincipal, *, start_at: datetime,
              end_at: datetime, duration_minutes: int = 30,
              step_minutes: int = 30) -> dict:
        start, end = _instant(start_at), _instant(end_at)
        if (type(duration_minutes) is not int or not 15 <= duration_minutes <= 480
            or type(step_minutes) is not int or not 15 <= step_minutes <= 240
            or end <= start or end - start > timedelta(days=7)):
            raise CRMConflict("agenda.range_invalid")
        with self._sessions() as db:
            rows = db.scalars(select(AgendaAppointmentORM).where(
                AgendaAppointmentORM.tenant_id == principal.tenant_id,
                AgendaAppointmentORM.unit_id == principal.unit_id,
                AgendaAppointmentORM.owner_user_id == principal.user_id,
                AgendaAppointmentORM.status == "scheduled",
                AgendaAppointmentORM.starts_at < end,
                AgendaAppointmentORM.ends_at > start,
            )).all()
            occupied = [(_utc_from_db(item.starts_at),
                         _utc_from_db(item.ends_at)) for item in rows]
        choices = []
        cursor = start
        while cursor + timedelta(minutes=duration_minutes) <= end and len(choices) < 97:
            finish = cursor + timedelta(minutes=duration_minutes)
            choices.append({
                "starts_at": cursor.isoformat(), "ends_at": finish.isoformat(),
                "available": not any(a < finish and b > cursor for a, b in occupied),
            })
            cursor += timedelta(minutes=step_minutes)
        return {"items": choices[:96], "has_more": len(choices) > 96}

    def mutate(self, principal: SessionPrincipal, *, appointment_id: str,
               expected_revision: int, action: str,
               starts_at: datetime | None = None,
               duration_minutes: int | None = None) -> dict:
        if type(expected_revision) is not int or expected_revision < 1:
            raise CRMConflict("agenda.revision_invalid")
        if action not in {"reschedule", "cancel", "complete"}:
            raise CRMConflict("agenda.action_invalid")
        start = end = None
        if action == "reschedule":
            if starts_at is None or duration_minutes is None:
                raise CRMConflict("agenda.schedule_invalid")
            start, end = self._bounds(starts_at, duration_minutes)
        instant = datetime.now(UTC)
        with self._sessions.begin() as db:
            self._locked_unit(db, principal)
            item = self._scoped(db, principal, appointment_id)
            if item.revision != expected_revision or item.status != "scheduled":
                raise CRMConflict("agenda.revision_conflict")
            if action == "reschedule":
                self._opportunity(db, principal, item.contact_id, item.opportunity_id)
                if self._busy(db, principal, start, end, exclude=appointment_id):
                    raise CRMConflict("agenda.slot_occupied")
                item.starts_at, item.ends_at = start, end
                item.remind_at = start - timedelta(minutes=item.remind_minutes) if item.remind_minutes else None
            else:
                item.status = "cancelled" if action == "cancel" else "completed"
            item.revision += 1
            item.updated_by, item.updated_at = principal.user_id, instant
            self._event(db, item, action, principal.user_id, instant)
            db.flush()
            return self._view(item)

    def events(self, principal: SessionPrincipal, *, appointment_id: str) -> dict:
        with self._sessions() as db:
            self._scoped(db, principal, appointment_id)
            rows = db.scalars(select(AgendaEventORM).where(
                AgendaEventORM.appointment_id == appointment_id,
                AgendaEventORM.tenant_id == principal.tenant_id,
                AgendaEventORM.unit_id == principal.unit_id,
            ).order_by(AgendaEventORM.created_at,
                       AgendaEventORM.event_id).limit(200)).all()
            return {"items": [{"action": row.action, "actor_id": row.actor_id,
                               "created_at": _utc_from_db(row.created_at).isoformat()}
                              for row in rows]}

    def reminders(self, *, now: datetime | None = None, limit: int = 50) -> dict:
        """Atomic scheduled-to-internal-CRM-task projection; replay creates no duplicate."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CRMConflict("agenda.batch_invalid")
        instant = _instant(now or datetime.now(UTC))
        sent = expired = closed = 0
        with self._sessions.begin() as db:
            query = select(AgendaAppointmentORM).where(
                AgendaAppointmentORM.status == "scheduled",
                AgendaAppointmentORM.remind_at.is_not(None),
                AgendaAppointmentORM.remind_at <= instant,
                AgendaAppointmentORM.reminder_revision < AgendaAppointmentORM.revision,
            ).order_by(AgendaAppointmentORM.remind_at,
                       AgendaAppointmentORM.appointment_id).limit(limit)
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            for item in db.scalars(query).all():
                opp = db.scalar(select(CRMOpportunityORM).where(
                    CRMOpportunityORM.opportunity_id == item.opportunity_id,
                    CRMOpportunityORM.contact_id == item.contact_id,
                    CRMOpportunityORM.tenant_id == item.tenant_id,
                    CRMOpportunityORM.unit_id == item.unit_id,
                ))
                item.reminder_revision = item.revision
                item.updated_at = instant
                if opp is None or opp.stage in {"won", "lost"}:
                    closed += 1
                    self._event(db, item, "reminder_blocked", "f7-agenda-worker", instant)
                elif _utc_from_db(item.starts_at) <= instant:
                    expired += 1
                    self._event(db, item, "reminder_expired", "f7-agenda-worker", instant)
                else:
                    db.add(CRMActivityORM(
                        activity_id=str(uuid4()), tenant_id=item.tenant_id,
                        unit_id=item.unit_id, opportunity_id=item.opportunity_id,
                        actor_id=item.owner_user_id, kind="task",
                        details_ciphertext=self._vault.encrypt(
                            "Lembrete interno de compromisso: "
                            + self._vault.decrypt(item.title_ciphertext)
                        ),
                        related_id=item.appointment_id,
                        created_at=instant,
                    ))
                    sent += 1
                    self._event(db, item, "reminded", "f7-agenda-worker", instant)
        return {"reminded": sent, "expired": expired, "blocked": closed}
