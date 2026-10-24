"""F7 deterministic cadence engine: durable CRM tasks, no external messaging.

Worker records *internal* encrypted CRM activities only. Provider dispatch is
intentionally not implemented: an ambiguous remote send must never auto-retry.
All claims use generation fencing, scoped policies, and atomic DB transitions.
"""
from __future__ import annotations

import json
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
    exists,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Mapped, aliased, mapped_column

from .crm import CRMConflict, CRMContactORM, CRMNotFound, CRMOpportunityORM
from .crm_workflow import CRMActivityORM
from .db import Base
from .followups import FollowupPreferenceORM, quiet_now
from .identity_repository import SessionPrincipal

_MAX_ATTEMPTS = 3
_LEASE = timedelta(seconds=120)
_RETRY_SECONDS = (60, 300, 1800)


class CadenceDefinitionORM(Base):
    __tablename__ = "assistant_cadence_definitions"

    cadence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    steps_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_cadence_def_scope", "tenant_id", "unit_id"),)


class CadenceRunORM(Base):
    __tablename__ = "assistant_cadence_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    cadence_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cadence_version: Mapped[int] = mapped_column(Integer, nullable=False)
    contact_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_contacts.contact_id"), nullable=False,
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_crm_opportunities.opportunity_id"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "unit_id", "idempotency_key",
                         name="uq_cadence_run_idempotency"),
        Index("ix_cadence_run_scope", "tenant_id", "unit_id", "contact_id"),
    )


class CadenceJobORM(Base):
    __tablename__ = "assistant_cadence_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_cadence_runs.run_id"), nullable=False,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(48))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_cadence_job_step"),
        Index("ix_cadence_due", "state", "available_at"),
    )


class CadenceEventORM(Base):
    __tablename__ = "assistant_cadence_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_cadence_runs.run_id"), nullable=False,
    )
    job_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index("ix_cadence_events_scope", "tenant_id", "unit_id", "run_id", "created_at"),
    )


def _utc(now: datetime | None) -> datetime:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        raise CRMConflict("cadence.naive_datetime")
    return value.astimezone(UTC)


def _db_time(dt: datetime) -> datetime:
    """UTC-aware at the database boundary; SQLite may deserialize naive UTC."""
    return dt.astimezone(UTC)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _view_task(row: CadenceJobORM) -> dict:
    return {
        "job_id": row.job_id, "step_index": row.step_index,
        "state": row.state, "attempt_count": row.attempt_count,
        "due_at": row.due_at.isoformat(), "available_at": row.available_at.isoformat(),
        "last_error": row.last_error,
    }


class CadenceEngine:
    def __init__(self, sessions, vault) -> None:
        self._sessions = sessions
        self._vault = vault

    @staticmethod
    def _event(db, run: CadenceRunORM, action: str, *, actor: str,
               job_id: str | None = None, code: str | None = None,
               now: datetime | None = None) -> None:
        db.add(CadenceEventORM(
            event_id=str(uuid4()), tenant_id=run.tenant_id, unit_id=run.unit_id,
            run_id=run.run_id, job_id=job_id, action=action,
            actor_id=actor, reason_code=code,
            created_at=_db_time(_utc(now)),
        ))

    @staticmethod
    def _definition(db, tenant: str, unit: str, cadence_id: str,
                    version: int | None = None):
        query = select(CadenceDefinitionORM).where(
            CadenceDefinitionORM.tenant_id == tenant,
            CadenceDefinitionORM.unit_id == unit,
            CadenceDefinitionORM.cadence_id == cadence_id,
        )
        if version is not None:
            query = query.where(CadenceDefinitionORM.version == version)
        else:
            query = query.order_by(CadenceDefinitionORM.version.desc()).limit(1)
        return db.scalar(query)

    @staticmethod
    def _validate_steps(channel: str, name: str, steps: list) -> None:
        if (channel not in {"whatsapp", "email"} or type(name) is not str
            or not 1 <= len(name.strip()) <= 120
            or type(steps) is not list or not 1 <= len(steps) <= 8):
            raise CRMConflict("cadence.definition_invalid")
        before = -1
        for step in steps:
            if type(step) is not dict or set(step) != {"delay_minutes", "task"}:
                raise CRMConflict("cadence.step_invalid")
            delay, task = step["delay_minutes"], step["task"]
            if (type(delay) is not int or not 0 <= delay <= 43200
                or delay <= before or type(task) is not str
                or not 1 <= len(task.strip()) <= 500):
                raise CRMConflict("cadence.step_invalid")
            before = delay

    def define(self, principal: SessionPrincipal, *, name: str, channel: str,
               steps: list, cadence_id: str | None = None,
               expected_version: int = 0) -> dict:
        self._validate_steps(channel, name, steps)
        if type(expected_version) is not int or expected_version < 0:
            raise CRMConflict("cadence.version_invalid")
        if (cadence_id is None and expected_version != 0
            or cadence_id is not None and expected_version < 1):
            raise CRMConflict("cadence.version_invalid")
        now = _db_time(datetime.now(UTC))
        cid = cadence_id or str(uuid4())
        try:
            with self._sessions.begin() as db:
                if cadence_id:
                    latest = self._definition(
                        db, principal.tenant_id, principal.unit_id, cid,
                    )
                    if latest is None:
                        raise CRMNotFound("cadence.definition_not_found")
                    if latest.version != expected_version:
                        raise CRMConflict("cadence.version_conflict")
                version = expected_version + 1
                db.add(CadenceDefinitionORM(
                    cadence_id=cid, version=version,
                    tenant_id=principal.tenant_id, unit_id=principal.unit_id,
                    name=name.strip(), channel=channel,
                    steps_ciphertext=self._vault.encrypt(json.dumps(
                        [{"delay_minutes": x["delay_minutes"], "task": x["task"].strip()}
                         for x in steps], ensure_ascii=False,
                    )), created_by=principal.user_id, created_at=now,
                ))
            return {"cadence_id": cid, "version": version,
                    "name": name.strip(), "channel": channel,
                    "steps_count": len(steps)}
        except IntegrityError as exc:
            raise CRMConflict("cadence.concurrent_version") from exc

    def list_definitions(self, principal: SessionPrincipal) -> dict:
        with self._sessions() as db:
            rows = db.scalars(select(CadenceDefinitionORM).where(
                CadenceDefinitionORM.tenant_id == principal.tenant_id,
                CadenceDefinitionORM.unit_id == principal.unit_id,
            ).order_by(CadenceDefinitionORM.cadence_id,
                       CadenceDefinitionORM.version.desc()).limit(200)).all()
            return {"items": [{
                "cadence_id": r.cadence_id, "version": r.version,
                "name": r.name, "channel": r.channel,
            } for r in rows]}

    @staticmethod
    def _scoped_run(db, principal: SessionPrincipal, run_id: str):
        row = db.scalar(select(CadenceRunORM).where(
            CadenceRunORM.run_id == run_id,
            CadenceRunORM.tenant_id == principal.tenant_id,
            CadenceRunORM.unit_id == principal.unit_id,
        ).with_for_update())
        if row is None:
            raise CRMNotFound("cadence.run_not_found")
        return row

    def schedule(self, principal: SessionPrincipal, *, cadence_id: str,
                 version: int, contact_id: str, opportunity_id: str,
                 idempotency_key: str, start_at: datetime, now: datetime | None = None) -> dict:
        instant = _utc(now)
        starting = _utc(start_at)
        if (type(version) is not int or version < 1
            or type(idempotency_key) is not str
            or not 8 <= len(idempotency_key) <= 128
            or starting > instant + timedelta(days=30)
            or starting < instant - timedelta(minutes=5)):
            raise CRMConflict("cadence.schedule_invalid")
        try:
            with self._sessions.begin() as db:
                prior = db.scalar(select(CadenceRunORM).where(
                    CadenceRunORM.tenant_id == principal.tenant_id,
                    CadenceRunORM.unit_id == principal.unit_id,
                    CadenceRunORM.idempotency_key == idempotency_key,
                ))
                if prior:
                    if (prior.cadence_id != cadence_id or prior.cadence_version != version
                        or prior.contact_id != contact_id
                        or prior.opportunity_id != opportunity_id
                        or starting != _as_utc(prior.start_at)):
                        raise CRMConflict("cadence.idempotency_mismatch")
                    return self._run_view(db, prior)
                definition = self._definition(
                    db, principal.tenant_id, principal.unit_id, cadence_id, version,
                )
                if definition is None:
                    raise CRMNotFound("cadence.definition_not_found")
                contact = db.scalar(select(CRMContactORM.contact_id).where(
                    CRMContactORM.contact_id == contact_id,
                    CRMContactORM.tenant_id == principal.tenant_id,
                    CRMContactORM.unit_id == principal.unit_id,
                ))
                opportunity = db.scalar(select(CRMOpportunityORM).where(
                    CRMOpportunityORM.opportunity_id == opportunity_id,
                    CRMOpportunityORM.contact_id == contact_id,
                    CRMOpportunityORM.tenant_id == principal.tenant_id,
                    CRMOpportunityORM.unit_id == principal.unit_id,
                ))
                if contact is None or opportunity is None:
                    raise CRMNotFound("cadence.contact_opportunity_not_found")
                if opportunity.stage in {"won", "lost"}:
                    raise CRMConflict("cadence.opportunity_closed")
                policy = db.scalar(select(FollowupPreferenceORM).where(
                    FollowupPreferenceORM.tenant_id == principal.tenant_id,
                    FollowupPreferenceORM.unit_id == principal.unit_id,
                    FollowupPreferenceORM.contact_id == contact_id,
                    FollowupPreferenceORM.channel == definition.channel,
                ))
                if policy is None or policy.opted_out:
                    raise CRMConflict("cadence.contact_not_eligible")
                steps = json.loads(self._vault.decrypt(definition.steps_ciphertext))
                run = CadenceRunORM(
                    run_id=str(uuid4()), tenant_id=principal.tenant_id,
                    unit_id=principal.unit_id, cadence_id=cadence_id,
                    cadence_version=version, contact_id=contact_id,
                    opportunity_id=opportunity_id, idempotency_key=idempotency_key,
                    start_at=_db_time(starting), status="active",
                    created_by=principal.user_id, created_at=_db_time(instant),
                )
                db.add(run)
                for index, step in enumerate(steps):
                    due = _db_time(starting + timedelta(minutes=step["delay_minutes"]))
                    db.add(CadenceJobORM(
                        job_id=str(uuid4()), run_id=run.run_id, step_index=index,
                        state="pending", due_at=due, available_at=due,
                        claim_generation=0, attempt_count=0, lease_until=None,
                        last_error=None, updated_at=_db_time(instant),
                    ))
                self._event(db, run, "scheduled", actor=principal.user_id, now=instant)
                db.flush()
                return self._run_view(db, run)
        except IntegrityError as exc:
            # Caller retries the same idempotency key to recover the canonical run.
            raise CRMConflict("cadence.concurrent_schedule") from exc

    @staticmethod
    def _run_view(db, run: CadenceRunORM) -> dict:
        jobs = db.scalars(select(CadenceJobORM).where(
            CadenceJobORM.run_id == run.run_id,
        ).order_by(CadenceJobORM.step_index)).all()
        return {
            "run_id": run.run_id, "status": run.status,
            "cadence_id": run.cadence_id, "version": run.cadence_version,
            "contact_id": run.contact_id, "opportunity_id": run.opportunity_id,
            "jobs": [_view_task(x) for x in jobs],
        }

    def list_runs(self, principal: SessionPrincipal, *,
                  status: str | None = None) -> dict:
        """Bounded tenant/unit-scoped operational queue; no decrypted task text."""
        allowed = {"active", "completed", "blocked", "failed", "cancelled"}
        if status is not None and status not in allowed:
            raise CRMConflict("cadence.status_invalid")
        with self._sessions() as db:
            query = select(CadenceRunORM).where(
                CadenceRunORM.tenant_id == principal.tenant_id,
                CadenceRunORM.unit_id == principal.unit_id,
            )
            if status:
                query = query.where(CadenceRunORM.status == status)
            rows = db.scalars(query.order_by(
                CadenceRunORM.created_at.desc(), CadenceRunORM.run_id.desc(),
            ).limit(51)).all()
            return {
                "items": [self._run_view(db, run) for run in rows[:50]],
                "has_more": len(rows) > 50,
            }

    def get_run(self, principal: SessionPrincipal, *, run_id: str) -> dict:
        with self._sessions() as db:
            run = self._scoped_run(db, principal, run_id)
            return self._run_view(db, run)

    def cancel(self, principal: SessionPrincipal, *, run_id: str) -> dict:
        with self._sessions.begin() as db:
            run = self._scoped_run(db, principal, run_id)
            if run.status == "active":
                run.status = "cancelled"
                db.execute(update(CadenceJobORM).where(
                    CadenceJobORM.run_id == run_id,
                    CadenceJobORM.state.in_(("pending", "leased")),
                ).values(state="cancelled", lease_until=None))
                self._event(db, run, "cancelled", actor=principal.user_id)
            return self._run_view(db, run)

    def events(self, principal: SessionPrincipal, *, run_id: str) -> dict:
        with self._sessions() as db:
            self._scoped_run(db, principal, run_id)
            rows = db.scalars(select(CadenceEventORM).where(
                CadenceEventORM.run_id == run_id,
                CadenceEventORM.tenant_id == principal.tenant_id,
                CadenceEventORM.unit_id == principal.unit_id,
            ).order_by(CadenceEventORM.created_at,
                       CadenceEventORM.event_id).limit(300)).all()
            return {"items": [{"action": x.action, "job_id": x.job_id,
                              "reason": x.reason_code, "created_at": x.created_at.isoformat()}
                             for x in rows]}

    def claim(self, *, now: datetime | None = None) -> tuple[str, int] | None:
        instant = _db_time(_utc(now))
        with self._sessions.begin() as db:
            # Enforce cadence order: a later step cannot overtake the prior step.
            previous = aliased(CadenceJobORM)
            query = select(CadenceJobORM).join(
                CadenceRunORM, CadenceJobORM.run_id == CadenceRunORM.run_id,
            ).where(
                CadenceJobORM.state == "pending",
                CadenceJobORM.available_at <= instant,
                CadenceRunORM.status == "active",
                ~exists(select(previous.job_id).where(
                    previous.run_id == CadenceJobORM.run_id,
                    previous.step_index < CadenceJobORM.step_index,
                    previous.state != "completed",
                )),
            ).order_by(CadenceJobORM.available_at, CadenceJobORM.job_id).limit(1)
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                query = query.with_for_update(of=CadenceJobORM, skip_locked=True)
            job = db.scalar(query)
            if job is None:
                return None
            generation = job.claim_generation + 1
            try:
                count = db.execute(update(CadenceJobORM).where(
                    CadenceJobORM.job_id == job.job_id,
                    CadenceJobORM.state == "pending",
                    CadenceJobORM.claim_generation == job.claim_generation,
                    CadenceJobORM.available_at <= instant,
                ).values(
                    state="leased", claim_generation=generation,
                    attempt_count=job.attempt_count + 1,
                    lease_until=instant + _LEASE, updated_at=instant,
                ).execution_options(synchronize_session=False)).rowcount
            except OperationalError:
                db.rollback()
                return None
            if count != 1:
                return None
            run = db.get(CadenceRunORM, job.run_id)
            self._event(db, run, "claimed", actor="f7-worker",
                        job_id=job.job_id, now=_utc(now))
            return job.job_id, generation

    def _leased(self, db, job_id: str, generation: int, instant: datetime):
        initial = db.get(CadenceJobORM, job_id)
        if initial is None:
            raise CRMConflict("cadence.lease_expired_or_fenced")
        # Lock order matches human cancellation: run first, then job.
        run = db.scalar(select(CadenceRunORM).where(
            CadenceRunORM.run_id == initial.run_id,
        ).with_for_update())
        job = db.scalar(select(CadenceJobORM).where(
            CadenceJobORM.job_id == job_id,
        ).with_for_update())
        if (job is None or job.state != "leased"
            or job.claim_generation != generation
            or job.lease_until is None
            or _as_utc(job.lease_until) <= _as_utc(instant)):
            raise CRMConflict("cadence.lease_expired_or_fenced")
        if run is None or run.status != "active":
            raise CRMConflict("cadence.run_inactive")
        return job, run

    def _block_followers(self, db, run: CadenceRunORM, job: CadenceJobORM,
                         instant: datetime, code: str) -> None:
        # Terminalize unexecuted downstream steps atomically.
        followers = db.scalars(select(CadenceJobORM).where(
            CadenceJobORM.run_id == run.run_id,
            CadenceJobORM.step_index > job.step_index,
            CadenceJobORM.state == "pending",
        ).with_for_update()).all()
        for follower in followers:
            follower.state = "blocked"
            follower.last_error = code
            follower.updated_at = instant
            self._event(db, run, "blocked", actor="f7-worker",
                        job_id=follower.job_id, code=code,
                        now=_as_utc(instant))

    def _retry_locked(self, db, job: CadenceJobORM, run: CadenceRunORM,
                      instant: datetime, code: str) -> str:
        if job.attempt_count >= _MAX_ATTEMPTS:
            job.state, job.lease_until = "dead", None
            run.status = "failed"
            self._block_followers(db, run, job, instant, "prior_step_dead")
            action = "dead_lettered"
        else:
            job.state, job.lease_until = "pending", None
            job.available_at = instant + timedelta(
                seconds=_RETRY_SECONDS[job.attempt_count - 1],
            )
            action = "retry_scheduled"
        job.last_error, job.updated_at = code, instant
        self._event(db, run, action, actor="f7-worker", job_id=job.job_id,
                    code=code, now=instant.replace(tzinfo=UTC))
        return job.state

    def fail(self, job_id: str, generation: int, *, code: str,
             now: datetime | None = None) -> str:
        if code not in {"internal_transient", "worker_interrupted"}:
            raise CRMConflict("cadence.failure_code_invalid")
        instant = _db_time(_utc(now))
        with self._sessions.begin() as db:
            job, run = self._leased(db, job_id, generation, instant)
            return self._retry_locked(db, job, run, instant, code)

    def recover(self, *, now: datetime | None = None, limit: int = 100) -> int:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise CRMConflict("cadence.recovery_limit_invalid")
        instant = _db_time(_utc(now))
        count = 0
        # One transaction per lease; CAS against concurrent claim/complete.
        with self._sessions.begin() as db:
            query = select(CadenceJobORM).where(
                CadenceJobORM.state == "leased",
                CadenceJobORM.lease_until <= instant,
            ).order_by(CadenceJobORM.lease_until, CadenceJobORM.job_id).limit(limit)
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            for job in db.scalars(query).all():
                run = db.get(CadenceRunORM, job.run_id)
                if run.status != "active":
                    job.state = "cancelled"
                    job.lease_until = None
                    self._event(db, run, "cancelled", actor="f7-worker",
                                job_id=job.job_id, now=_utc(now))
                else:
                    self._retry_locked(db, job, run, instant, "worker_interrupted")
                count += 1
        return count

    def execute(self, job_id: str, generation: int, *,
                now: datetime | None = None) -> str:
        """One atomic DB transaction creates at most one internal CRM task.

        No SMTP, WhatsApp, provider call or external side effect occurs here.
        """
        instant_utc = _utc(now)
        instant = _db_time(instant_utc)
        with self._sessions.begin() as db:
            job, run = self._leased(db, job_id, generation, instant)
            definition = self._definition(
                db, run.tenant_id, run.unit_id,
                run.cadence_id, run.cadence_version,
            )
            opp = db.scalar(select(CRMOpportunityORM).where(
                CRMOpportunityORM.opportunity_id == run.opportunity_id,
                CRMOpportunityORM.contact_id == run.contact_id,
                CRMOpportunityORM.tenant_id == run.tenant_id,
                CRMOpportunityORM.unit_id == run.unit_id,
            ))
            policy = db.scalar(select(FollowupPreferenceORM).where(
                FollowupPreferenceORM.tenant_id == run.tenant_id,
                FollowupPreferenceORM.unit_id == run.unit_id,
                FollowupPreferenceORM.contact_id == run.contact_id,
                FollowupPreferenceORM.channel == definition.channel,
            ).with_for_update())
            if (opp is None or opp.stage in {"won", "lost"}
                or policy is None or policy.opted_out):
                code = ("opportunity_closed" if opp is not None
                        and opp.stage in {"won", "lost"} else "contact_suppressed")
                job.state, job.lease_until = "blocked", None
                job.last_error, job.updated_at = code, instant
                run.status = "blocked"
                self._block_followers(db, run, job, instant, "prior_step_blocked")
                self._event(db, run, "blocked", actor="f7-worker",
                            job_id=job.job_id, code=code, now=instant_utc)
                return "blocked"
            if quiet_now(
                instant_utc, policy.timezone,
                policy.quiet_start_minute, policy.quiet_end_minute,
            ):
                # Delay for 15 minutes at a time, recheck the latest policy each tick.
                # No customer messaging or task generated during quiet time.
                job.state, job.lease_until = "pending", None
                job.available_at, job.updated_at = instant + timedelta(minutes=15), instant
                self._event(db, run, "quiet_deferred", actor="f7-worker",
                            job_id=job.job_id, now=instant_utc)
                return "quiet_deferred"
            steps = json.loads(self._vault.decrypt(definition.steps_ciphertext))
            if not 0 <= job.step_index < len(steps):
                raise CRMConflict("cadence.corrupt_step")
            # Explicit CAS fencing before the business effect; both commit together.
            changed = db.execute(update(CadenceJobORM).where(
                CadenceJobORM.job_id == job_id,
                CadenceJobORM.state == "leased",
                CadenceJobORM.claim_generation == generation,
                CadenceJobORM.lease_until > instant,
            ).values(state="completed", lease_until=None, updated_at=instant)
                .execution_options(synchronize_session=False)).rowcount
            if changed != 1:
                raise CRMConflict("cadence.lease_expired_or_fenced")
            db.add(CRMActivityORM(
                activity_id=str(uuid4()), tenant_id=run.tenant_id,
                unit_id=run.unit_id, opportunity_id=run.opportunity_id,
                actor_id="f7-worker", kind="task",
                details_ciphertext=self._vault.encrypt(steps[job.step_index]["task"]),
                related_id=job.job_id, created_at=instant,
            ))
            self._event(db, run, "completed", actor="f7-worker",
                        job_id=job.job_id, now=instant_utc)
            unfinished = db.scalar(select(CadenceJobORM.job_id).where(
                CadenceJobORM.run_id == run.run_id,
                CadenceJobORM.job_id != job_id,
                CadenceJobORM.state != "completed",
            ).limit(1))
            if unfinished is None:
                run.status = "completed"
                self._event(db, run, "run_completed", actor="f7-worker",
                            now=instant_utc)
            return "completed"

    def tick(self, *, now: datetime | None = None, batch: int = 10) -> dict:
        if type(batch) is not int or not 1 <= batch <= 100:
            raise CRMConflict("cadence.batch_invalid")
        recovered = self.recover(now=now, limit=batch)
        outcomes: dict[str, int] = {}
        for _ in range(batch):
            claim = self.claim(now=now)
            if claim is None:
                break
            job_id, generation = claim
            try:
                outcome = self.execute(job_id, generation, now=now)
            except (OperationalError, IntegrityError):
                # Only atomic DB operations are used; ambiguous commit is not
                # automatically replayed in the same tick.
                outcome = "error"
                try:
                    self.fail(job_id, generation, code="internal_transient", now=now)
                except (CRMConflict, OperationalError):
                    pass
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        return {"recovered": recovered, "outcomes": outcomes}
