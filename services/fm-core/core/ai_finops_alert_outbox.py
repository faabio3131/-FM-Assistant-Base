"""FM-owned persistent FinOps alert outbox: deterministic, bounded and off by default.

Scanning is explicitly invoked by an authorized internal operator/scheduler.
It does not dispatch messages, settle provider invoices or release reservations.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256

from sqlalchemy import DateTime, Index, Integer, String, and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from core.ai_admin_audit import stage_admin_mutation_audit
from core.ai_command_authority import VerifiedCommandAdmin
from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_finops_alerts import evaluate_request_cost_alert
from core.ai_finops_policy_store import PersistentFinOpsAlertPolicies
from core.ai_usage_ledger import PersistentAIFinOps


class AIFinOpsAlertOutboxRecord(ControlPlaneBase):
    __tablename__ = "core_ai_finops_alert_outbox"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    reasons_json: Mapped[str] = mapped_column(String(500), nullable=False)
    known_cost_subtotal: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    unknown_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_core_finops_alert_outbox_scope",
            "tenant_id", "unit_id", "status", "created_at",
        ),
    )


@dataclass(frozen=True)
class FinOpsAlertScanResult:
    created: int
    scanned: int
    next_cursor: str | None


@dataclass(frozen=True)
class FinOpsAlertPage:
    items: tuple[AIFinOpsAlertOutboxRecord, ...]
    next_cursor: str | None


class PersistentFinOpsAlertOutbox:
    """Materialize existing authoritative evidence, never extrapolate spend."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions
        self._policies = PersistentFinOpsAlertPolicies(sessions)
        self._ledger = PersistentAIFinOps(sessions)

    def scan(
        self, *, tenant_id: str, unit_id: str, start_date: date,
        end_date: date, limit: int = 50, after_request_id: str | None = None,
    ) -> FinOpsAlertScanResult:
        # Reuse the ledger's strict scope, window, cursor and limit validator.
        ids, cursor = self._ledger.listar_ids_solicitacoes(
            tenant_id=tenant_id, unit_id=unit_id, inicio=start_date,
            fim=end_date, after_request_id=after_request_id, limit=limit,
        )
        policy = self._policies.get(tenant_id=tenant_id, unit_id=unit_id)
        if policy is None or not policy.enabled:
            return FinOpsAlertScanResult(created=0, scanned=len(ids), next_cursor=cursor)

        candidates: list[AIFinOpsAlertOutboxRecord] = []
        for request_id in ids:
            summary = self._ledger.reconcile_request(
                tenant_id=tenant_id, unit_id=unit_id, request_id=request_id,
            )
            try:
                evaluation = evaluate_request_cost_alert(
                    summary, maximum_known_cost=policy.maximum_known_cost,
                    currency=policy.currency,
                )
            except ValueError as exc:
                # Mixed denominations must never become a silent zero alert.
                raise ControlPlaneError("core_finops.alert_currency_mismatch") from exc
            if not evaluation.reasons:
                continue
            canonical = {
                "tenant_id": tenant_id, "unit_id": unit_id,
                "request_id": request_id, "revision": policy.revision,
                "reasons": list(evaluation.reasons),
                "known_cost": str(evaluation.known_cost),
                "currency": evaluation.cost_currency,
                "unknown_attempts": evaluation.unknown_attempts,
                "observed_attempts": evaluation.observed_attempts,
            }
            event_id = sha256(json.dumps(
                canonical, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()
            candidates.append(AIFinOpsAlertOutboxRecord(
                event_id=event_id, tenant_id=tenant_id, unit_id=unit_id,
                request_id=request_id, policy_revision=policy.revision,
                reasons_json=json.dumps(canonical["reasons"], separators=(",", ":")),
                known_cost_subtotal=str(evaluation.known_cost),
                currency=evaluation.cost_currency,
                unknown_attempts=evaluation.unknown_attempts,
                observed_attempts=evaluation.observed_attempts,
                status="pending", created_at=datetime.now(UTC), reviewed_at=None,
            ))

        created = 0
        with self._sessions.begin() as db:
            for event in candidates:
                if db.get(AIFinOpsAlertOutboxRecord, event.event_id) is not None:
                    continue
                try:
                    # Contending schedulers cannot duplicate an identical alert.
                    with db.begin_nested():
                        db.add(event)
                        db.flush()
                except IntegrityError as exc:
                    if db.get(AIFinOpsAlertOutboxRecord, event.event_id) is None:
                        raise ControlPlaneError(
                            "core_finops.alert_outbox_write_conflict"
                        ) from exc
                    continue
                created += 1
        return FinOpsAlertScanResult(
            created=created, scanned=len(ids), next_cursor=cursor,
        )

    def page_pending(
        self, *, tenant_id: str, unit_id: str, limit: int = 50,
        after_event_id: str | None = None,
    ) -> FinOpsAlertPage:
        self._policies.get(tenant_id=tenant_id, unit_id=unit_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ControlPlaneError("core_finops.alert_outbox_limit_invalid")
        if after_event_id is not None and (
            type(after_event_id) is not str or len(after_event_id) != 64
            or any(c not in "0123456789abcdef" for c in after_event_id)
        ):
            raise ControlPlaneError("core_finops.alert_outbox_cursor_invalid")
        with self._sessions() as db:
            predicates = [
                AIFinOpsAlertOutboxRecord.tenant_id == tenant_id,
                AIFinOpsAlertOutboxRecord.unit_id == unit_id,
                AIFinOpsAlertOutboxRecord.status == "pending",
            ]
            if after_event_id is not None:
                # Scope and cursor authority live in Core, not in an FMCC UI.
                anchor = db.scalar(
                    select(AIFinOpsAlertOutboxRecord).where(
                        AIFinOpsAlertOutboxRecord.event_id == after_event_id,
                        AIFinOpsAlertOutboxRecord.tenant_id == tenant_id,
                        AIFinOpsAlertOutboxRecord.unit_id == unit_id,
                    )
                )
                if anchor is None:
                    raise ControlPlaneError("core_finops.alert_outbox_cursor_invalid")
                predicates.append(or_(
                    AIFinOpsAlertOutboxRecord.created_at > anchor.created_at,
                    and_(
                        AIFinOpsAlertOutboxRecord.created_at == anchor.created_at,
                        AIFinOpsAlertOutboxRecord.event_id > anchor.event_id,
                    ),
                ))
            rows = tuple(db.scalars(
                select(AIFinOpsAlertOutboxRecord).where(*predicates).order_by(
                    AIFinOpsAlertOutboxRecord.created_at,
                    AIFinOpsAlertOutboxRecord.event_id,
                ).limit(limit + 1)
            ).all())
            page = rows[:limit]
            return FinOpsAlertPage(
                items=page,
                next_cursor=page[-1].event_id if len(rows) > limit else None,
            )

    def list_pending(
        self, *, tenant_id: str, unit_id: str, limit: int = 50,
    ) -> tuple[AIFinOpsAlertOutboxRecord, ...]:
        return self.page_pending(
            tenant_id=tenant_id, unit_id=unit_id, limit=limit,
        ).items

    def mark_reviewed(
        self, *, event_id: str, tenant_id: str, unit_id: str,
        principal: VerifiedCommandAdmin,
    ) -> bool:
        if (
            type(event_id) is not str or len(event_id) != 64
            or any(c not in "0123456789abcdef" for c in event_id)
            or not isinstance(principal, VerifiedCommandAdmin)
            or "core.ai.admin.mutate" not in principal.permissions
        ):

            raise ControlPlaneError("core_finops.alert_review_denied")
        self._policies.get(tenant_id=tenant_id, unit_id=unit_id)
        with self._sessions.begin() as db:
            event = db.scalar(select(AIFinOpsAlertOutboxRecord).where(
                AIFinOpsAlertOutboxRecord.event_id == event_id,
                AIFinOpsAlertOutboxRecord.tenant_id == tenant_id,
                AIFinOpsAlertOutboxRecord.unit_id == unit_id,
            ).with_for_update())
            if event is None:
                raise ControlPlaneError("core_finops.alert_not_found")
            if event.status == "reviewed":
                return False
            if event.status != "pending":
                raise ControlPlaneError("core_finops.alert_status_invalid")
            event.status = "reviewed"
            event.reviewed_at = datetime.now(UTC)
            stage_admin_mutation_audit(
                db, principal=principal, action="finops.alert.review",
                resource_id=event_id,
                canonical_request=json.dumps({
                    "event_id": event_id, "tenant_id": event.tenant_id,
                    "unit_id": event.unit_id,
                }, sort_keys=True, separators=(",", ":")).encode(),
            )
        return True
