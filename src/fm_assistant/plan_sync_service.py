"""FM-governed commercial plan projection into Assistant local license catalog.

Only a separately authenticated Command signing identity can call apply().
No tenant is permitted to change catalog rows, features or prices. Prices are
not stored here: Command remains the only commercial price authority.
"""
from __future__ import annotations

import hmac
import json
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .command_bridge_control_service import sign_command_control
from .db import PlanLimitORM, PlanSyncNonceORM, PlanVersionORM

PATH = "/internal/v1/command/assistant-plans/project"
KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{22,96}$")
METRICS = frozenset({
    "ai.requests", "ai.total_tokens", "ai.input_tokens",
    "ai.output_tokens", "ai.cached_tokens", "ai.cost_usd_microunits",
    "audio.seconds", "whatsapp.messages", "automation.executions",
    "storage.bytes", "crm.leads", "users.seats", "units.active",
})


class PlanSyncDenied(PermissionError):
    pass


class CommandPlanProjectionService:
    def __init__(
        self, *, sessions, key_id: str | None, signing_key: str | None,
        trusted_organization: str | None,
    ) -> None:
        self._sessions = sessions
        self._key_id = key_id
        self._key = signing_key
        self._organization = trusted_organization

    def apply(
        self, *, headers: dict[str, str | None], raw_body: bytes,
        organization_id: str, actor_user_id: str, step_up_at: int,
        product_code: str, plan_code: str, revision: int, label: str,
        allowances: tuple[dict[str, object], ...],
    ) -> str:
        now = datetime.now(UTC)
        timestamp = headers.get("timestamp") or ""
        nonce = headers.get("nonce") or ""
        signature = headers.get("signature") or ""
        key_id = headers.get("key_id") or ""
        if (
            not self._key_id or not self._key or len(self._key) < 32
            or not self._organization or len(raw_body) > 12000
            or key_id != self._key_id or not NONCE.fullmatch(nonce)
            or len(signature) != 64
            or not timestamp.isascii() or not timestamp.isdecimal()
            or len(timestamp) != 10
            or abs(int(now.timestamp()) - int(timestamp)) > 60
            or organization_id != self._organization
            or product_code != "VENDEATENDEIA"
            or not KEY.fullmatch(actor_user_id) or type(step_up_at) is not int
            or step_up_at > int(now.timestamp()) + 15
            or int(now.timestamp()) - step_up_at > 300
            or not KEY.fullmatch(plan_code) or len(plan_code) > 120
            or type(revision) is not int or revision < 1
            or not isinstance(label, str)
            or not 2 <= len(label.strip()) <= 160
            or not 1 <= len(allowances) <= 32
        ):
            raise PlanSyncDenied("plan_sync_denied")
        expected = sign_command_control(
            key=self._key, key_id=key_id, timestamp=timestamp,
            nonce=nonce, body=raw_body, path=PATH,
        )
        if not hmac.compare_digest(expected, signature):
            raise PlanSyncDenied("plan_sync_denied")
        try:
            decoded = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PlanSyncDenied("plan_sync_denied") from exc
        if decoded != {
            "product_code": product_code,
            "organization_id": organization_id,
            "actor_user_id": actor_user_id,
            "step_up_at": step_up_at,
            "plan_code": plan_code,
            "revision": revision,
            "label": label,
            "allowances": list(allowances),
        }:
            raise PlanSyncDenied("plan_sync_denied")

        clean: dict[str, tuple[str, int, int]] = {}
        for entry in allowances:
            if not isinstance(entry, dict) or set(entry) != {
                "resource", "scope", "limitUnits", "windowSeconds",
            }:
                raise PlanSyncDenied("plan_sync_denied")
            resource = entry["resource"]
            scope = entry["scope"]
            amount = entry["limitUnits"]
            window = entry["windowSeconds"]
            if (
                not isinstance(resource, str) or resource not in METRICS
                or resource in clean or scope not in {"tenant", "unit"}
                or type(amount) is not int or amount <= 0 or amount > 9_000_000_000_000_000
                or type(window) is not int or not 60 <= window <= 366 * 86400
            ):
                raise PlanSyncDenied("plan_sync_denied")
            clean[resource] = (scope, amount, window)
        if not {"ai.requests", "ai.total_tokens"}.issubset(clean):
            raise PlanSyncDenied("plan_sync_denied")

        try:
            with self._sessions.begin() as db:
                db.add(PlanSyncNonceORM(key_id=key_id, nonce=nonce, created_at=now))
                db.flush()  # replay fails before any catalog mutation
                key = (plan_code, revision)
                version = db.get(PlanVersionORM, key)
                existing = db.scalars(select(PlanLimitORM).where(
                    PlanLimitORM.plan_code == plan_code,
                    PlanLimitORM.revision == revision,
                )).all()
                if version is not None:
                    previous = {
                        item.resource: (item.scope, item.limit_units, item.window_seconds)
                        for item in existing
                    }
                    if (
                        version.label != label.strip()
                        or version.status not in {"published", "retired"}
                        or previous != clean
                    ):
                        raise PlanSyncDenied("plan_sync_denied")
                    return "already_projected"
                db.add(PlanVersionORM(
                    plan_code=plan_code, revision=revision,
                    label=label.strip(), status="published", created_at=now,
                ))
                for resource, (scope, amount, window) in clean.items():
                    db.add(PlanLimitORM(
                        plan_code=plan_code, revision=revision,
                        resource=resource, scope=scope, limit_units=amount,
                        window_seconds=window,
                    ))
                db.flush()
                return "projected"
        except IntegrityError as exc:
            raise PlanSyncDenied("plan_sync_denied") from exc
