"""F7 first slice: human-governed contact suppression and local quiet hours.

No scheduler, dispatch or provider integration here. Missing policy denies sends.
Future workers must re-evaluate this policy immediately before dispatch.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint,
    select, update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from .crm import CRMAuditORM, CRMConflict, CRMContactORM, CRMNotFound
from .db import Base
from .identity_repository import SessionPrincipal


class FollowupPreferenceORM(Base):
    __tablename__ = "assistant_followup_preferences"

    preference_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_contacts.contact_id"), nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    opted_out: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    quiet_start_minute: Mapped[int] = mapped_column(Integer(), nullable=False)
    quiet_end_minute: Mapped[int] = mapped_column(Integer(), nullable=False)
    revision: Mapped[int] = mapped_column(Integer(), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "unit_id", "contact_id", "channel",
            name="uq_followup_policy_scope_contact_channel",
        ),
        Index("ix_followup_policy_scope", "tenant_id", "unit_id", "contact_id"),
    )


def _minute(clock: str) -> int:
    if (type(clock) is not str or len(clock) != 5
        or clock[2] != ":" or not (clock[:2] + clock[3:]).isdigit()):
        raise CRMConflict("followup.clock_invalid")
    hh, mm = int(clock[:2]), int(clock[3:])
    if hh > 23 or mm > 59:
        raise CRMConflict("followup.clock_invalid")
    return hh * 60 + mm


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def quiet_now(now: datetime, timezone: str, start: int, end: int) -> bool:
    """Local clock quiet interval; UTC instant resolves DST offset correctly."""
    if now.tzinfo is None:
        raise CRMConflict("followup.now_naive")
    local = now.astimezone(ZoneInfo(timezone))
    minute = local.hour * 60 + local.minute
    if start < end:
        return start <= minute < end
    # Overnight interval: e.g. 22:00 through 08:00.
    return minute >= start or minute < end


class FollowupPreferences:
    def __init__(self, sessions) -> None:
        self._sessions = sessions

    @staticmethod
    def _contact(db, principal: SessionPrincipal, contact_id: str) -> None:
        match = db.scalar(select(CRMContactORM.contact_id).where(
            CRMContactORM.contact_id == contact_id,
            CRMContactORM.tenant_id == principal.tenant_id,
            CRMContactORM.unit_id == principal.unit_id,
        ))
        if match is None:
            raise CRMNotFound("followup.contact_not_found")

    @staticmethod
    def _policy(db, principal: SessionPrincipal, contact_id: str,
                channel: str):
        return db.scalar(select(FollowupPreferenceORM).where(
            FollowupPreferenceORM.tenant_id == principal.tenant_id,
            FollowupPreferenceORM.unit_id == principal.unit_id,
            FollowupPreferenceORM.contact_id == contact_id,
            FollowupPreferenceORM.channel == channel,
        ).with_for_update())

    @staticmethod
    def _channel(channel: str) -> None:
        if channel not in {"whatsapp", "email"}:
            raise CRMConflict("followup.channel_invalid")

    @staticmethod
    def _view(row: FollowupPreferenceORM | None, channel: str,
              now: datetime) -> dict:
        if row is None:
            return {
                "configured": False, "channel": channel, "revision": 0,
                "opted_out": None, "timezone": None,
                "quiet_start": None, "quiet_end": None,
                "can_dispatch": False, "reason": "unconfigured",
            }
        blocked = quiet_now(
            now, row.timezone, row.quiet_start_minute, row.quiet_end_minute,
        )
        reason = "opted_out" if row.opted_out else (
            "quiet_hours" if blocked else "eligible"
        )
        return {
            "configured": True, "channel": channel, "revision": row.revision,
            "opted_out": row.opted_out, "timezone": row.timezone,
            "quiet_start": _clock(row.quiet_start_minute),
            "quiet_end": _clock(row.quiet_end_minute),
            "can_dispatch": reason == "eligible", "reason": reason,
        }

    def get(self, principal: SessionPrincipal, *, contact_id: str,
            channel: str, now: datetime | None = None) -> dict:
        self._channel(channel)
        with self._sessions() as db:
            self._contact(db, principal, contact_id)
            row = self._policy(db, principal, contact_id, channel)
            return self._view(row, channel, now or datetime.now(UTC))

    def configure(
        self, principal: SessionPrincipal, *, contact_id: str,
        channel: str, expected_revision: int, opted_out: bool,
        timezone: str, quiet_start: str, quiet_end: str,
    ) -> dict:
        self._channel(channel)
        if (type(expected_revision) is not int
            or not 0 <= expected_revision <= 2_000_000_000
            or type(opted_out) is not bool
            or type(timezone) is not str or not 1 <= len(timezone) <= 64):
            raise CRMConflict("followup.policy_invalid")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
            raise CRMConflict("followup.timezone_invalid") from exc
        start = _minute(quiet_start)
        end = _minute(quiet_end)
        if start == end:
            raise CRMConflict("followup.quiet_interval_invalid")
        now = datetime.now(UTC)
        try:
            with self._sessions.begin() as db:
                self._contact(db, principal, contact_id)
                row = self._policy(db, principal, contact_id, channel)
                if row is None:
                    if expected_revision != 0:
                        raise CRMConflict("followup.revision_conflict")
                    row = FollowupPreferenceORM(
                        preference_id=str(uuid4()),
                        tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                        contact_id=contact_id, channel=channel,
                        opted_out=opted_out, timezone=timezone,
                        quiet_start_minute=start, quiet_end_minute=end,
                        revision=1, updated_by=principal.user_id, updated_at=now,
                    )
                    db.add(row)
                else:
                    if row.opted_out and not opted_out:
                        # Human update alone is not verifiable customer opt-in.
                        raise CRMConflict("followup.consent_evidence_required")
                    changed = db.execute(update(FollowupPreferenceORM).where(
                        FollowupPreferenceORM.preference_id == row.preference_id,
                        FollowupPreferenceORM.tenant_id == principal.tenant_id,
                        FollowupPreferenceORM.unit_id == principal.unit_id,
                        FollowupPreferenceORM.revision == expected_revision,
                    ).values(
                        opted_out=opted_out, timezone=timezone,
                        quiet_start_minute=start, quiet_end_minute=end,
                        revision=expected_revision + 1,
                        updated_by=principal.user_id, updated_at=now,
                    )).rowcount
                    if changed != 1:
                        raise CRMConflict("followup.revision_conflict")
                    db.refresh(row)
                db.add(CRMAuditORM(
                    event_id=str(uuid4()), tenant_id=principal.tenant_id,
                    unit_id=principal.unit_id, actor_id=principal.user_id,
                    entity_kind="followup", entity_id=contact_id,
                    action="policy_updated", created_at=now,
                ))
                db.flush()
                return self._view(row, channel, now)
        except IntegrityError as exc:
            raise CRMConflict("followup.concurrent_update") from exc
