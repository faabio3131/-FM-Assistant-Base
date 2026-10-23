"""F3.8 quota policy ledger regression with synthetic units only."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import ControlPlaneBase
from core.ai_quota_store import (
    AIQuotaPolicyRecord,
    AIQuotaReservationRecord,
    QuotaDenied,
    QuotaRequirement,
    QuotaReservations,
    ReservationState,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def quota(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'quotas.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        for tenant, unit, limit in (("a", "u1", 3), ("a", "u2", 1), ("b", "u1", 1), ("b", "u2", 1)):
            db.add(AIQuotaPolicyRecord(
                tenant_id=tenant, unit_id=unit, capability="text",
                limit_units=limit, window_seconds=60, revision=1,
            ))
    yield QuotaReservations(sessions), sessions
    engine.dispose()


def reserve(store, rid, *, tenant="a", unit="u1", units=1, at=NOW):
    return store.reserve(
        tenant_id=tenant, unit_id=unit, capability="text",
        request_id=rid, units=units, at=at,
    )


def settle(store, rid, *, tenant="a", unit="u1", consumed=0):
    return store.settle(
        tenant_id=tenant, unit_id=unit, capability="text",
        request_id=rid, consumed_units=consumed,
    )


def test_reservation_idempotency_conflict_and_quota_cap(quota):
    store, sessions = quota
    one = reserve(store, "request-1", units=2)
    assert one.state == ReservationState.RESERVED
    assert reserve(store, "request-1", units=2).request_id == one.request_id
    with pytest.raises(QuotaDenied, match="request_conflict"):
        reserve(store, "request-1", units=1)
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "request-2", units=2)
    assert reserve(store, "request-2", units=1).reserved_units == 1
    with sessions() as db:
        assert len(db.scalars(select(AIQuotaReservationRecord)).all()) == 2


def test_settlement_refund_and_double_settlement_are_idempotent(quota):
    store, _ = quota
    reserve(store, "first", units=3)
    assert settle(store, "first", consumed=1).state == ReservationState.SETTLED
    assert settle(store, "first", consumed=1).consumed_units == 1
    with pytest.raises(QuotaDenied, match="settlement_conflict"):
        settle(store, "first", consumed=2)
    assert reserve(store, "second", units=2).state == ReservationState.RESERVED
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "third", units=1)
    settle(store, "second", consumed=0)
    assert reserve(store, "third", units=1).state == ReservationState.RESERVED


def test_no_cross_scope_release_or_shared_budget(quota):
    store, _ = quota
    reserve(store, "same-id", tenant="a", unit="u1", units=3)
    reserve(store, "same-id", tenant="b", unit="u1")
    reserve(store, "same-id", tenant="a", unit="u2")
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        settle(store, "same-id", tenant="b", unit="u2")
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "another", tenant="b", unit="u1")


def test_request_id_cannot_shift_to_next_period(quota):
    store, _ = quota
    reserve(store, "same", units=1)
    with pytest.raises(QuotaDenied, match="request_conflict"):
        reserve(store, "same", units=1, at=NOW + timedelta(minutes=2))
    assert reserve(store, "next", units=3, at=NOW + timedelta(minutes=2)).period != (
        reserve(store, "same").period
    )


def test_fail_closed_for_bad_policy_or_request(quota):
    store, _ = quota
    with pytest.raises(QuotaDenied, match="policy_unavailable"):
        reserve(store, "unknown", tenant="missing")
    with pytest.raises(QuotaDenied, match="invalid_scope"):
        reserve(store, "../spoofed")
    with pytest.raises(QuotaDenied, match="invalid_units"):
        reserve(store, "test", units=0)
    with pytest.raises(QuotaDenied, match="invalid_units"):
        reserve(store, "test", units=True)
    with pytest.raises(QuotaDenied, match="time_invalid"):
        reserve(store, "test", at=datetime(2026, 10, 18))
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        settle(store, "never")
    reserve(store, "only", units=1)
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        settle(store, "only", consumed=2)


def test_request_replay_after_policy_revision_is_rejected(quota):
    store, sessions = quota
    reserve(store, "prior", units=1)
    with sessions.begin() as db:
        policy = db.get(AIQuotaPolicyRecord, ("a", "u1", "text"))
        policy.revision = 2
        policy.limit_units = 1
    with pytest.raises(QuotaDenied, match="request_conflict"):
        reserve(store, "prior", units=1)
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        reserve(store, "new", units=1)


def test_pending_quota_reconciliation_is_scoped_read_only(quota):
    store, sessions = quota
    reserve(store, "ambiguous", units=1, tenant="a", unit="u1")
    reserve(store, "other-tenant", tenant="b", unit="u1")
    reserve(store, "success", units=1, tenant="a", unit="u1")
    settle(store, "success", consumed=1, tenant="a", unit="u1")
    cutoff = NOW + timedelta(minutes=1)
    pending = store.pending_for_reconciliation(
        tenant_id="a", unit_id="u1", capability="text", older_than=cutoff,
    )
    assert [p.request_id for p in pending] == ["ambiguous"]
    assert store.pending_for_reconciliation(
        tenant_id="a", unit_id="u2", capability="text", older_than=cutoff,
    ) == ()
    assert [p.request_id for p in store.pending_for_reconciliation(
        tenant_id="b", unit_id="u1", capability="text", older_than=cutoff,
    )] == ["other-tenant"]
    with pytest.raises(QuotaDenied, match="invalid_limit"):
        store.pending_for_reconciliation(
            tenant_id="a", unit_id="u1", capability="text",
            older_than=cutoff, limit=1000,
        )
    with sessions() as db:
        records = db.scalars(select(AIQuotaReservationRecord)).all()
        assert len(records) == 3  # query did not modify/erase reservations


def test_atomic_multimetric_plan_reservation_and_settlement(quota):
    store, sessions = quota
    with sessions.begin() as db:
        for scope, metric, limit in (
            ("__tenant__", "ai.total_tokens", 1000),
            ("u1", "ai.requests", 2),
        ):
            db.add(AIQuotaPolicyRecord(
                tenant_id="a", unit_id=scope, capability=metric,
                limit_units=limit, window_seconds=60, revision=1,
            ))
    needs = (
        QuotaRequirement(
            tenant_id="a", unit_id="__tenant__",
            capability="ai.total_tokens", units=600,
        ),
        QuotaRequirement(
            tenant_id="a", unit_id="u1", capability="ai.requests", units=1,
        ),
    )
    store.reserve_bundle(needs=needs, request_id="req-metric", at=NOW)
    with pytest.raises(QuotaDenied, match="execution_replay_denied"):
        store.reserve_bundle(needs=needs, request_id="req-metric", at=NOW)
    with pytest.raises(QuotaDenied, match="limit_exceeded"):
        store.reserve_bundle(
            needs=(
                QuotaRequirement(
                    tenant_id="a", unit_id="__tenant__",
                    capability="ai.total_tokens", units=600,
                ),
                QuotaRequirement(
                    tenant_id="a", unit_id="u1", capability="ai.requests", units=1,
                ),
            ),
            request_id="req-over", at=NOW,
        )
    with sessions() as db:
        assert len(db.scalars(
            select(AIQuotaReservationRecord).where(
                AIQuotaReservationRecord.request_id == "req-over",
            ),
        ).all()) == 0  # failure rolled back every metric

    store.settle_bundle(
        request_id="req-metric",
        usage=(
            QuotaRequirement(
                tenant_id="a", unit_id="__tenant__",
                capability="ai.total_tokens", units=350,
            ),
            QuotaRequirement(
                tenant_id="a", unit_id="u1", capability="ai.requests", units=1,
            ),
        ),
    )
    store.reserve_bundle(
        needs=(
            QuotaRequirement(
                tenant_id="a", unit_id="__tenant__",
                capability="ai.total_tokens", units=650,
            ),
        ),
        request_id="next-request", at=NOW,
    )
    with pytest.raises(QuotaDenied, match="settlement_conflict"):
        store.settle_bundle(
            request_id="req-metric",
            usage=(
                QuotaRequirement(
                    tenant_id="a", unit_id="__tenant__",
                    capability="ai.total_tokens", units=200,
                ),
            ),
        )


def test_bundle_cross_tenant_and_partial_settlement_denied(quota):
    store, sessions = quota
    with pytest.raises(QuotaDenied, match="bundle_invalid"):
        store.reserve_bundle(
            needs=(
                QuotaRequirement(
                    tenant_id="a", unit_id="u1", capability="text", units=1,
                ),
                QuotaRequirement(
                    tenant_id="b", unit_id="u1", capability="text", units=1,
                ),
            ),
            request_id="cross-tenant", at=NOW,
        )
    store.reserve_bundle(
        needs=(
            QuotaRequirement(tenant_id="a", unit_id="u1", capability="text", units=1),
            QuotaRequirement(tenant_id="a", unit_id="u2", capability="text", units=1),
        ),
        request_id="multi-scope", at=NOW,
    )
    with pytest.raises(QuotaDenied, match="reservation_unavailable"):
        store.settle_bundle(
            request_id="multi-scope",
            usage=(
                QuotaRequirement(tenant_id="a", unit_id="u1", capability="text", units=1),
                QuotaRequirement(tenant_id="a", unit_id="u2", capability="text", units=2),
            ),
        )
    with sessions() as db:
        records = db.scalars(
            select(AIQuotaReservationRecord).where(
                AIQuotaReservationRecord.request_id == "multi-scope",
            ),
        ).all()
        assert len(records) == 2
        assert all(record.state == ReservationState.RESERVED for record in records)


def test_plan_usage_snapshot_reports_remaining_and_pending_reservations(quota):
    store, _ = quota
    reserve(store, "first", units=2)
    before = store.usage_snapshot(
        tenant_id="a", unit_id="u1", capability="text", at=NOW,
    )
    assert (before.limit_units, before.reserved_units, before.consumed_units) == (3, 2, 0)
    assert before.remaining_units == 1
    assert before.period_ends_at > NOW
    settle(store, "first", consumed=1)
    after = store.usage_snapshot(
        tenant_id="a", unit_id="u1", capability="text", at=NOW,
    )
    assert (after.reserved_units, after.consumed_units, after.remaining_units) == (0, 1, 2)
    other = store.usage_snapshot(
        tenant_id="b", unit_id="u1", capability="text", at=NOW,
    )
    assert (other.reserved_units, other.consumed_units, other.remaining_units) == (0, 0, 1)
    with pytest.raises(QuotaDenied, match="policy_unavailable"):
        store.usage_snapshot(
            tenant_id="missing", unit_id="u1", capability="text", at=NOW,
        )


def test_bundle_revision_fence_rejects_stale_policy_atomically(quota):
    store, sessions = quota
    with pytest.raises(QuotaDenied, match="policy_revision_mismatch"):
        store.reserve_bundle(
            needs=(QuotaRequirement(
                tenant_id="a", unit_id="u1", capability="text",
                units=1, policy_revision=2,
            ),), request_id="stale-revision", at=NOW,
        )
    with sessions() as db:
        assert db.get(AIQuotaReservationRecord, ("a", "u1", "text", "stale-revision")) is None
    with pytest.raises(QuotaDenied, match="bundle_invalid"):
        store.reserve_bundle(
            needs=(QuotaRequirement(
                tenant_id="a", unit_id="u1", capability="text",
                units=1, policy_revision=True,
            ),), request_id="bad-revision", at=NOW,
        )


def test_signed_grants_project_atomically_and_preserve_usage(quota):
    store, sessions = quota
    grants = (
        ("ai.requests", "tenant", 5, 86400),
        ("ai.total_tokens", "tenant", 1000, 86400),
    )
    store.project_signed_grants(tenant_id="a", unit_id="u1", revision=3, grants=grants)
    store.project_signed_grants(tenant_id="a", unit_id="u1", revision=3, grants=grants)
    snapshot = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__", capability="ai.total_tokens", at=NOW,
    )
    assert snapshot.limit_units == 1000
    assert snapshot.policy_revision == 3
    store.reserve_bundle(
        needs=(QuotaRequirement(
            tenant_id="a", unit_id="__tenant__", capability="ai.total_tokens",
            units=400, policy_revision=3,
        ),), request_id="prior-use", at=NOW,
    )
    with pytest.raises(QuotaDenied, match="projection_conflict"):
        store.project_signed_grants(
            tenant_id="a", unit_id="u1", revision=3,
            grants=(("ai.requests", "tenant", 5, 86400),
                    ("ai.total_tokens", "tenant", 2000, 86400)),
        )
    with pytest.raises(QuotaDenied, match="projection_stale"):
        store.project_signed_grants(
            tenant_id="a", unit_id="u1", revision=2, grants=grants,
        )
    store.project_signed_grants(
        tenant_id="a", unit_id="u1", revision=4,
        grants=(("ai.requests", "tenant", 5, 86400),
                ("ai.total_tokens", "tenant", 500, 86400)),
    )
    updated = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__", capability="ai.total_tokens", at=NOW,
    )
    assert (updated.limit_units, updated.reserved_units, updated.remaining_units) == (
        500, 400, 100,
    )
    with sessions() as db:
        assert len(db.scalars(select(AIQuotaReservationRecord).where(
            AIQuotaReservationRecord.request_id == "prior-use",
        )).all()) == 1


def test_projector_denies_malformed_or_partial_grants(quota):
    store, _ = quota
    cases = [
        (("ai.requests", "tenant", True, 60),
         ("ai.total_tokens", "tenant", 100, 60)),
        (("ai.requests", "tenant", 1, 60),
         ("ai.requests", "tenant", 2, 60)),
        (("ai.requests", "customer", 1, 60),
         ("ai.total_tokens", "tenant", 100, 60)),
    ]
    for grants in cases:
        with pytest.raises(QuotaDenied, match="projection_invalid"):
            store.project_signed_grants(
                tenant_id="a", unit_id="u1", revision=3, grants=grants,
            )


def test_signed_revision_cannot_change_period_window_after_usage(quota):
    store, sessions = quota
    previous = (
        ("ai.requests", "tenant", 5, 60),
        ("ai.total_tokens", "tenant", 500, 60),
    )
    store.project_signed_grants(
        tenant_id="a", unit_id="u1", revision=3, grants=previous,
    )
    store.reserve_bundle(
        needs=(QuotaRequirement(
            tenant_id="a", unit_id="__tenant__",
            capability="ai.total_tokens", units=200, policy_revision=3,
        ),), request_id="unfinished", at=NOW,
    )
    with pytest.raises(QuotaDenied, match="projection_window_change_blocked"):
        store.project_signed_grants(
            tenant_id="a", unit_id="u1", revision=4,
            grants=(("ai.requests", "tenant", 5, 60),
                    ("ai.total_tokens", "tenant", 800, 3600)),
        )
    with sessions() as db:
        request_policy = db.get(
            AIQuotaPolicyRecord, ("a", "__tenant__", "ai.requests"),
        )
        token_policy = db.get(
            AIQuotaPolicyRecord, ("a", "__tenant__", "ai.total_tokens"),
        )
        assert request_policy.revision == 3  # entire projection rolled back
        assert (token_policy.revision, token_policy.window_seconds) == (3, 60)
    with pytest.raises(QuotaDenied, match="projection_window_change_blocked"):
        store.project_signed_grants(
            tenant_id="a", unit_id="u1", revision=4,
            grants=(("ai.requests", "tenant", 5, 60),
                    ("ai.total_tokens", "tenant", 800, 3600)),
        )
    assert store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    ).reserved_units == 200


def test_evidence_backed_recovery_is_atomic_audited_and_replay_safe(quota):
    from core.ai_admin_audit import CommandAdminAuditRecord
    from core.ai_command_authority import VerifiedCommandAdmin

    store, sessions = quota
    store.reserve_bundle(
        needs=(
            QuotaRequirement(tenant_id="a", unit_id="u1",
                             capability="text", units=2, policy_revision=1),
            QuotaRequirement(tenant_id="a", unit_id="u2",
                             capability="text", units=1, policy_revision=1),
        ),
        request_id="ambiguous-one", at=NOW,
    )
    def principal(token):
        return VerifiedCommandAdmin(
            user_id="operator-1", session_id="operator-session",
            token_id=token, issued_at=int(NOW.timestamp()) - 10,
            expires_at=int(NOW.timestamp()) + 90,
            step_up_at=int(NOW.timestamp()) - 10,
            permissions=frozenset({"core.ai.admin.mutate"}),
        )
    consumption = (
        QuotaRequirement(tenant_id="a", unit_id="u1",
                         capability="text", units=1, policy_revision=1),
        QuotaRequirement(tenant_id="a", unit_id="u2",
                         capability="text", units=1, policy_revision=1),
    )
    with pytest.raises(QuotaDenied, match="recovery_partial_bundle"):
        store.reconcile_ambiguous_bundle(
            usage=consumption[:1], request_id="ambiguous-one",
            principal=principal("token-a"), evidence_digest="a" * 64,
            evidence_kind="provider_usage_confirmed", at=NOW,
        )
    with pytest.raises(QuotaDenied, match="recovery_evidence_mismatch"):
        store.reconcile_ambiguous_bundle(
            usage=consumption, request_id="ambiguous-one",
            principal=principal("token-a"), evidence_digest="a" * 64,
            evidence_kind="provider_no_charge_confirmed", at=NOW,
        )
    store.reconcile_ambiguous_bundle(
        usage=consumption, request_id="ambiguous-one",
        principal=principal("token-a"), evidence_digest="a" * 64,
        evidence_kind="provider_usage_confirmed", at=NOW,
    )
    with sessions() as db:
        records = db.scalars(select(AIQuotaReservationRecord).where(
            AIQuotaReservationRecord.request_id == "ambiguous-one",
        )).all()
        assert len(records) == 2
        assert all(row.state == ReservationState.SETTLED for row in records)
        assert sorted(row.consumed_units for row in records) == [1, 1]
        audits = db.scalars(select(CommandAdminAuditRecord)).all()
        assert len(audits) == 1
        assert audits[0].action == "core.ai.quota.reconcile"
        assert len(audits[0].request_digest) == 64
    with pytest.raises(QuotaDenied, match="recovery_conflict"):
        store.reconcile_ambiguous_bundle(
            usage=consumption, request_id="ambiguous-one",
            principal=principal("token-b"), evidence_digest="a" * 64,
            evidence_kind="provider_usage_confirmed", at=NOW,
        )


def test_no_charge_attestation_only_releases_verified_full_bundle(quota):
    from core.ai_command_authority import VerifiedCommandAdmin

    store, _ = quota
    reserve(store, "certainly-no-charge", units=3)
    principal = VerifiedCommandAdmin(
        user_id="human", session_id="session", token_id="no-charge-jti",
        issued_at=int(NOW.timestamp()) - 5,
        expires_at=int(NOW.timestamp()) + 60,
        step_up_at=int(NOW.timestamp()) - 5,
        permissions=frozenset({"core.ai.admin.mutate"}),
    )
    with pytest.raises(QuotaDenied, match="recovery_evidence_invalid"):
        store.reconcile_ambiguous_bundle(
            usage=(QuotaRequirement(tenant_id="a", unit_id="u1",
                                    capability="text", units=0,
                                    policy_revision=1),),
            request_id="certainly-no-charge", principal=principal,
            evidence_digest="unverified", evidence_kind="provider_no_charge_confirmed",
            at=NOW,
        )
    store.reconcile_ambiguous_bundle(
        usage=(QuotaRequirement(tenant_id="a", unit_id="u1",
                                capability="text", units=0,
                                policy_revision=1),),
        request_id="certainly-no-charge", principal=principal,
        evidence_digest="f" * 64, evidence_kind="provider_no_charge_confirmed",
        at=NOW,
    )
    assert store.usage_snapshot(
        tenant_id="a", unit_id="u1", capability="text", at=NOW,
    ).remaining_units == 3


def test_verified_provider_receipt_settles_canonical_core_reservation_once(quota):
    """No parallel Assistant ledger, no inferred usage and no double charge."""
    from decimal import Decimal

    from core.ai_admin_audit import CommandAdminAuditRecord
    from core.ai_command_authority import VerifiedCommandAdmin
    from core.ai_verified_usage_receipt import VerifiedProviderUsageReceipt

    store, sessions = quota
    with sessions.begin() as db:
        for metric, bound in (("ai.requests", 50), ("ai.total_tokens", 1000)):
            db.add(AIQuotaPolicyRecord(
                tenant_id="a", unit_id="__tenant__", capability=metric,
                limit_units=bound, window_seconds=60, revision=7,
            ))
    reserved = (
        QuotaRequirement(
            tenant_id="a", unit_id="__tenant__", capability="ai.requests",
            units=1, policy_revision=7,
        ),
        QuotaRequirement(
            tenant_id="a", unit_id="__tenant__", capability="ai.total_tokens",
            units=400, policy_revision=7,
        ),
    )
    store.reserve_bundle(needs=reserved, request_id="provider-confirmed", at=NOW)
    before = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert before.reserved_units == 400 and before.consumed_units == 0
    principal = VerifiedCommandAdmin(
        user_id="fm-human-admin", session_id="fm-session",
        token_id="token-provider-confirmed-123456789",
        issued_at=int(NOW.timestamp()) - 3,
        expires_at=int(NOW.timestamp()) + 120,
        step_up_at=int(NOW.timestamp()) - 3,
        permissions=frozenset({"core.ai.admin.mutate"}),
    )
    receipt = VerifiedProviderUsageReceipt(
        tenant_id="a", unit_id="u1", provider="gemini", model="gemini-model",
        request_id="provider-confirmed", input_tokens=140, output_tokens=60,
        provider_cost_usd=Decimal("0.015"),
        evidence_digest="d" * 64,
    )
    store.reconcile_verified_provider_receipt(
        receipt=receipt, request_policy_revision=7, tokens_policy_revision=7,
        principal=principal, at=NOW,
    )
    after = store.usage_snapshot(
        tenant_id="a", unit_id="__tenant__",
        capability="ai.total_tokens", at=NOW,
    )
    assert after.reserved_units == 0
    assert after.consumed_units == 200
    with sessions() as db:
        assert len(db.scalars(select(CommandAdminAuditRecord).where(
            CommandAdminAuditRecord.action == "core.ai.quota.reconcile",
        )).all()) == 1
    with pytest.raises(QuotaDenied, match="core_quota.recovery_conflict"):
        store.reconcile_verified_provider_receipt(
            receipt=receipt, request_policy_revision=7,
            tokens_policy_revision=7, principal=principal, at=NOW,
        )
