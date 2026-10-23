"""F3 durable alert generation: policies, deduplication, staff review and API."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.ai_admin_audit import CommandAdminAuditRecord
from core.ai_admin_read_api import register_admin_read_routes
from core.ai_command_authority import VerifiedCommandAdmin
from core.ai_control_plane import ControlPlaneBase, ControlPlaneError
from core.ai_finops_alert_outbox import (
    AIFinOpsAlertOutboxRecord,
    PersistentFinOpsAlertOutbox,
)
from core.ai_finops_policy_store import PersistentFinOpsAlertPolicies
from core.ai_usage_ledger import AIRequestCostSummary


def principal(jti: str = "fm-alert-create-test-001") -> VerifiedCommandAdmin:
    return VerifiedCommandAdmin(
        user_id="human-fm", session_id="fm-session", token_id=jti,
        issued_at=100, expires_at=200, step_up_at=100,
        permissions=frozenset({"core.ai.admin.mutate"}),
    )


def summary(
    request_id: str, amount: str | None,
) -> AIRequestCostSummary:
    return AIRequestCostSummary(
        tenant_id="tenant-a", unit_id="unit-a", request_id=request_id,
        currency="USD" if amount is not None else None,
        known_total=Decimal(amount) if amount is not None else Decimal(0),
        known_attempts=1 if amount is not None else 0,
        unknown_attempts=0 if amount is not None else 1,
        total_attempts=1, fallback_attempts=0,
        all_recorded_costs_known=amount is not None,
    )


class SyntheticLedger:
    def __init__(self) -> None:
        self.records = {
            "high": summary("high", "0.06"),
            "low": summary("low", "0.01"),
            "unknown": summary("unknown", None),
        }

    def listar_ids_solicitacoes(self, *, tenant_id, unit_id, inicio, fim,
                               after_request_id=None, limit=50):
        assert tenant_id == "tenant-a" and unit_id == "unit-a"
        assert inicio <= fim and 1 <= limit <= 100
        keys = sorted(self.records)
        if after_request_id:
            keys = [key for key in keys if key > after_request_id]
        return tuple(keys[:limit]), keys[limit - 1] if len(keys) > limit else None

    def reconcile_request(self, *, tenant_id, unit_id, request_id):
        assert tenant_id == "tenant-a" and unit_id == "unit-a"
        return self.records[request_id]


@pytest.fixture
def harness(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'finops-alerts.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    policy = PersistentFinOpsAlertPolicies(sessions)
    outbox = PersistentFinOpsAlertOutbox(sessions)
    source = SyntheticLedger()
    outbox._ledger = source
    yield engine, sessions, policy, outbox, source
    engine.dispose()


def enable(policy: PersistentFinOpsAlertPolicies, *, expected=0, enabled=True,
           jti="fm-alert-create-test-001"):
    return policy.update(
        tenant_id="tenant-a", unit_id="unit-a",
        expected_revision=expected, enabled=enabled,
        currency="USD", maximum_known_cost=Decimal("0.05"),
        principal=principal(jti),
    )


def scan(outbox: PersistentFinOpsAlertOutbox, **options):
    return outbox.scan(
        tenant_id="tenant-a", unit_id="unit-a",
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 22),
        **options,
    )


def test_alerts_materialize_only_with_enabled_policy_and_dedupe(harness):
    _, sessions, policy, outbox, _ = harness
    assert scan(outbox).created == 0  # Opt-in OFF without an FM policy.
    enable(policy)
    first = scan(outbox)
    assert (first.created, first.scanned, first.next_cursor) == (2, 3, None)
    assert scan(outbox).created == 0
    rows = outbox.list_pending(tenant_id="tenant-a", unit_id="unit-a")
    assert len(rows) == 2
    assert {row.request_id for row in rows} == {"high", "unknown"}
    for row in rows:
        assert row.known_cost_subtotal in {"0.06", "0"}
        assert row.status == "pending"
        assert row.policy_revision == 1
    assert outbox.list_pending(tenant_id="tenant-a", unit_id="different") == ()
    assert outbox.list_pending(tenant_id="different", unit_id="unit-a") == ()
    with sessions() as db:
        assert len(db.scalars(select(AIFinOpsAlertOutboxRecord)).all()) == 2


def test_bounded_pages_policy_revisions_and_missing_cost_remain_unknown(harness):
    _, _, policy, outbox, source = harness
    enable(policy)
    first = scan(outbox, limit=1)
    assert first.created == 1 and first.next_cursor == "high"
    second = scan(outbox, limit=1, after_request_id=first.next_cursor)
    assert second.created == 0 and second.next_cursor == "low"
    third = scan(outbox, limit=1, after_request_id=second.next_cursor)
    assert third.created == 1 and third.next_cursor is None
    unknown = next(
        item for item in outbox.list_pending(
            tenant_id="tenant-a", unit_id="unit-a",
        ) if item.request_id == "unknown"
    )
    assert unknown.known_cost_subtotal == "0"
    assert unknown.unknown_attempts == 1
    assert "provider_cost_unverified" in unknown.reasons_json
    # A new attempt changes the immutable evidence and yields one new alert.
    source.records["high"] = replace(
        source.records["high"], known_total=Decimal("0.07"),
    )
    assert scan(outbox).created == 1
    assert scan(outbox).created == 0
    enable(policy, expected=1, enabled=False, jti="fm-alert-disable-test-002")
    assert scan(outbox).created == 0


def test_review_is_fm_only_audited_and_cannot_create_double_send(harness):
    _, sessions, policy, outbox, _ = harness
    enable(policy)
    scan(outbox)
    first = outbox.list_pending(tenant_id="tenant-a", unit_id="unit-a")[0]
    with pytest.raises(ControlPlaneError, match="review_denied"):
        outbox.mark_reviewed(
            event_id=first.event_id, tenant_id="tenant-a", unit_id="unit-a",
            principal=replace(principal(), permissions=frozenset()),
        )
    assert outbox.mark_reviewed(
        event_id=first.event_id, tenant_id="tenant-a", unit_id="unit-a",
        principal=principal("fm-alert-review-test-003"),
    )
    assert outbox.mark_reviewed(
        event_id=first.event_id, tenant_id="tenant-a", unit_id="unit-a",
        principal=principal("fm-alert-review-test-004"),
    ) is False
    assert len(outbox.list_pending(tenant_id="tenant-a", unit_id="unit-a")) == 1
    assert scan(outbox).created == 0
    with sessions() as db:
        row = db.get(AIFinOpsAlertOutboxRecord, first.event_id)
        assert row.status == "reviewed" and row.reviewed_at is not None
        audits = db.scalars(select(CommandAdminAuditRecord)).all()
        assert len(audits) == 2
        assert {item.action for item in audits} == {
            "finops.alert_policy.update", "finops.alert.review",
        }


def test_currency_mismatch_fails_closed_without_partial_queue(harness):
    _, sessions, policy, outbox, source = harness
    enable(policy)
    source.records["unknown"] = replace(
        source.records["unknown"],
        currency="EUR", known_total=Decimal("0.20"),
        known_attempts=1, unknown_attempts=0,
    )
    with pytest.raises(ControlPlaneError, match="alert_currency_mismatch"):
        scan(outbox)
    with sessions() as db:
        assert db.scalars(select(AIFinOpsAlertOutboxRecord)).all() == []


def test_operator_api_is_read_only_authenticated_and_tenant_scoped(harness):
    engine, _, policy, outbox, _ = harness
    enable(policy)
    scan(outbox)
    app = FastAPI()
    app.state.control_plane_engine = engine
    app.state.settings = SimpleNamespace(
        persistent_control_plane=True, admin_key="synthetic-operator-secret",
    )
    register_admin_read_routes(app)
    client = TestClient(app)
    path = "/v1/admin/ai/usage/alerts/outbox"
    params = {"tenant_id": "tenant-a", "unit_id": "unit-a"}
    assert client.get(path, params=params).status_code == 401
    r = client.get(
        path, params=params, headers={"X-Core-Admin-Key": "synthetic-operator-secret"},
    )
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    payload = r.json()
    assert payload["automated_dispatch_enabled"] is False
    assert payload["provider_invoice_verified"] is False
    assert len(payload["items"]) == 2
    assert {x["request_id"] for x in payload["items"]} == {"high", "unknown"}
    foreign = client.get(
        path, params={**params, "tenant_id": "foreign"},
        headers={"X-Core-Admin-Key": "synthetic-operator-secret"},
    )
    assert foreign.status_code == 200 and foreign.json()["items"] == []


def test_keyset_alert_pagination_exceeds_first_50_and_rejects_foreign_cursor(harness):
    _, sessions, policy, outbox, _ = harness
    enable(policy)
    from datetime import UTC, datetime, timedelta

    with sessions.begin() as db:
        timestamp = datetime.now(UTC)
        for index in range(123):
            db.add(AIFinOpsAlertOutboxRecord(
                event_id=f"{index:064x}", tenant_id="tenant-a", unit_id="unit-a",
                request_id=f"request-{index:03}", policy_revision=1,
                reasons_json='["provider_cost_unverified"]',
                known_cost_subtotal="0", currency=None, unknown_attempts=1,
                observed_attempts=1, status="pending",
                created_at=timestamp + timedelta(seconds=index // 7),
                reviewed_at=None,
            ))
        db.add(AIFinOpsAlertOutboxRecord(
            event_id="f" * 64, tenant_id="foreign", unit_id="unit-a",
            request_id="secret", policy_revision=1,
            reasons_json='["provider_cost_unverified"]',
            known_cost_subtotal="0", currency=None, unknown_attempts=1,
            observed_attempts=1, status="pending", created_at=timestamp,
            reviewed_at=None,
        ))
    cursor = None
    collected = []
    for page_no in range(3):
        page = outbox.page_pending(
            tenant_id="tenant-a", unit_id="unit-a", limit=50,
            after_event_id=cursor,
        )
        collected.extend(item.event_id for item in page.items)
        cursor = page.next_cursor
        if page_no < 2:
            assert cursor is not None
        else:
            assert cursor is None
    assert len(collected) == len(set(collected)) == 123
    assert collected == [f"{i:064x}" for i in range(123)]
    with pytest.raises(ControlPlaneError, match="cursor_invalid"):
        outbox.page_pending(
            tenant_id="tenant-a", unit_id="unit-a", after_event_id="f" * 64,
        )
    with pytest.raises(ControlPlaneError, match="cursor_invalid"):
        outbox.page_pending(
            tenant_id="tenant-a", unit_id="unit-a", after_event_id="../foreign",
        )
    with pytest.raises(ControlPlaneError, match="alert_not_found"):
        outbox.mark_reviewed(
            event_id=collected[0], tenant_id="other",
            unit_id="unit-a", principal=principal(),
        )
    with pytest.raises(ControlPlaneError, match="alert_not_found"):
        outbox.mark_reviewed(
            event_id="f" * 64, tenant_id="tenant-a",
            unit_id="unit-a", principal=principal(),
        )
    assert outbox.mark_reviewed(
        event_id=collected[0], tenant_id="tenant-a",
        unit_id="unit-a", principal=principal("review-paginated-001"),
    )
    next_page = outbox.page_pending(
        tenant_id="tenant-a", unit_id="unit-a", limit=50,
    )
    assert collected[0] not in [item.event_id for item in next_page.items]
