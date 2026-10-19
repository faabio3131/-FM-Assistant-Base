"""Plan quotas are licensed by the Assistant, never invented by the Core."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fm_assistant.db import (
    Base,
    PlanLimitORM,
    PlanVersionORM,
    TenantLicenseORM,
    TenantORM,
    UnitORM,
)
from fm_assistant.plan_limits import PlanLimitDenied, PlanLimitResolver
from fm_assistant.plan_policy_manifest import (
    LicensedQuotaManifestService,
    authenticated_core_plan_grant,
    issue_core_plan_grant,
)

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


@pytest.fixture
def catalog(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'plans.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        for tenant, unit, revision in (
            ("tenant-a", "unit-1", 1),
            ("tenant-b", "unit-1", 2),
        ):
            db.add(TenantORM(
                tenant_id=tenant, display_name=tenant,
                slug=tenant, status="active", created_at=NOW, updated_at=NOW,
            ))
            db.add(UnitORM(
                tenant_id=tenant, unit_id=unit, display_name=unit,
                status="active", created_at=NOW, updated_at=NOW,
            ))
            db.add(TenantLicenseORM(
                tenant_id=tenant, plan_code="business",
                plan_revision=revision, status="active",
                trial_started_at=None, trial_ends_at=None,
                period_started_at=NOW - timedelta(days=1),
                period_ends_at=NOW + timedelta(days=29),
                created_at=NOW, updated_at=NOW,
            ))
        for revision, cap in ((1, 1000), (2, 2000)):
            db.add(PlanVersionORM(
                plan_code="business", revision=revision, label="Business",
                status="published", created_at=NOW,
            ))
            db.add(PlanLimitORM(
                plan_code="business", revision=revision,
                resource="ai.total_tokens",
                scope="tenant", limit_units=cap, window_seconds=86400,
            ))
    yield PlanLimitResolver(sessions), sessions
    engine.dispose()


def test_plan_revision_pinned_and_tenant_isolated(catalog):
    resolver, _ = catalog
    a = resolver.resolve(
        tenant_id="tenant-a", unit_id="unit-1",
        resource="ai.total_tokens", now=NOW,
    )
    b = resolver.resolve(
        tenant_id="tenant-b", unit_id="unit-1",
        resource="ai.total_tokens", now=NOW,
    )
    assert (a.plan_code, a.revision, a.limit_units, a.scope) == (
        "business", 1, 1000, "tenant",
    )
    assert (b.plan_code, b.revision, b.limit_units, b.scope) == (
        "business", 2, 2000, "tenant",
    )
    assert a.licensed_until > NOW


def test_missing_metric_inactive_plan_and_cross_tenant_fail_closed(catalog):
    resolver, sessions = catalog
    for kw in (
        {"tenant_id": "tenant-a", "unit_id": "unit-b", "resource": "ai.total_tokens"},
        {"tenant_id": "tenant-b", "unit_id": "missing", "resource": "ai.total_tokens"},
        {"tenant_id": "tenant-a", "unit_id": "unit-1", "resource": "not-allowed"},
    ):
        with pytest.raises(PlanLimitDenied):
            resolver.resolve(**kw, now=NOW)
    with sessions.begin() as db:
        version = db.get(PlanVersionORM, ("business", 1))
        version.status = "draft"
    with pytest.raises(PlanLimitDenied):
        resolver.resolve(
            tenant_id="tenant-a", unit_id="unit-1",
            resource="ai.total_tokens", now=NOW,
        )


def test_plan_revision_and_subscription_expiry_cannot_be_bypassed(catalog):
    resolver, sessions = catalog
    with sessions.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.plan_revision = None
    with pytest.raises(PlanLimitDenied):
        resolver.resolve(
            tenant_id="tenant-a", unit_id="unit-1",
            resource="ai.total_tokens", now=NOW,
        )
    with sessions.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.plan_revision = 1
        license_row.period_ends_at = NOW
    with pytest.raises(PlanLimitDenied, match="period_expired"):
        resolver.resolve(
            tenant_id="tenant-a", unit_id="unit-1",
            resource="ai.total_tokens", now=NOW,
        )


def test_trial_without_expiry_and_suspended_subscription_denied(catalog):
    resolver, sessions = catalog
    with sessions.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.status = "trial"
        license_row.trial_ends_at = None
    with pytest.raises(PlanLimitDenied, match="period_unavailable"):
        resolver.resolve(
            tenant_id="tenant-a", unit_id="unit-1",
            resource="ai.total_tokens", now=NOW,
        )
    with sessions.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.status = "suspended"
    with pytest.raises(PlanLimitDenied):
        resolver.resolve(
            tenant_id="tenant-a", unit_id="unit-1",
            resource="ai.total_tokens", now=NOW,
        )


def test_manifest_matches_exact_pinned_subscription_revision(catalog):
    _, sessions = catalog
    with sessions.begin() as db:
        for revision in (1, 2):
            db.add(PlanLimitORM(
                plan_code="business", revision=revision,
                resource="ai.requests", scope="tenant",
                limit_units=100 * revision, window_seconds=86400,
            ))
    manifest = LicensedQuotaManifestService(sessions)
    first = manifest.resolve(tenant_id="tenant-a", unit_id="unit-1", now=NOW)
    second = manifest.resolve(tenant_id="tenant-b", unit_id="unit-1", now=NOW)
    assert first.revision == 1 and second.revision == 2
    assert first.plan_code == second.plan_code
    assert {g.resource for g in first.grants} == {"ai.requests", "ai.total_tokens"}
    assert next(g.limit_units for g in first.grants if g.resource=="ai.total_tokens") == 1000
    assert next(g.limit_units for g in second.grants if g.resource=="ai.total_tokens") == 2000
    assert first.policy_fingerprint() != second.policy_fingerprint()
    with sessions.begin() as db:
        license_row=db.get(TenantLicenseORM,"tenant-a")
        license_row.status="suspended"
    with pytest.raises(PlanLimitDenied):
        manifest.resolve(tenant_id="tenant-a", unit_id="unit-1", now=NOW)


def test_core_grant_derived_from_license_and_signed(catalog):
    import hashlib
    import hmac
    import json

    _, sessions = catalog
    with sessions.begin() as db:
        db.add(PlanLimitORM(
            plan_code="business", revision=1,
            resource="ai.requests", scope="tenant",
            limit_units=100, window_seconds=86400,
        ))
    source = LicensedQuotaManifestService(sessions)
    manifest = source.resolve(tenant_id="tenant-a", unit_id="unit-1", now=NOW)
    secret = b"assistant-to-core-test-secret-key-32-bytes-12345"
    body, signature = issue_core_plan_grant(
        manifest=manifest, capability="atendimento_interpretacao",
        input_bound=100, output_bound=50, secret=secret, now=NOW,
        challenge="test-challenge-0123456789abcdef",
    )
    assert hmac.compare_digest(
        signature,
        hmac.new(
            secret, b"/internal/v1/assistant/core-plan-grant\n" + body,
            hashlib.sha256,
        ).hexdigest(),
    )
    decoded = json.loads(body)
    assert decoded["challenge"] == "test-challenge-0123456789abcdef"
    assert decoded["revision"] == 1
    assert decoded["tenant_id"] == "tenant-a"
    assert decoded["expires_at"] - int(NOW.timestamp()) == 30
    with pytest.raises(PlanLimitDenied, match="bounds_exceeded"):
        issue_core_plan_grant(
            manifest=manifest, capability="atendimento_interpretacao",
            input_bound=900, output_bound=200, secret=secret, now=NOW,
            challenge="test-challenge-0123456789abcdef",
        )
    with sessions.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.status = "suspended"
    with pytest.raises(PlanLimitDenied):
        source.resolve(tenant_id="tenant-a", unit_id="unit-1", now=NOW)


def test_signed_core_grant_requires_fresh_valid_challenge(catalog):
    _, sessions = catalog
    with sessions.begin() as db:
        db.add(PlanLimitORM(
            plan_code="business", revision=1,
            resource="ai.requests", scope="tenant",
            limit_units=100, window_seconds=86400,
        ))
    manifest = LicensedQuotaManifestService(sessions).resolve(
        tenant_id="tenant-a", unit_id="unit-1", now=NOW,
    )
    for challenge in ("", "short", "spaces not allowed", "../traversal"):
        with pytest.raises(PlanLimitDenied, match="grant_denied"):
            issue_core_plan_grant(
                manifest=manifest, capability="atendimento_interpretacao",
                input_bound=100, output_bound=50,
                secret=b"assistant-to-core-test-secret-key-32-bytes-12345",
                now=NOW, challenge=challenge,
            )


def test_authenticated_core_policy_request_and_live_revocation(catalog):
    import hashlib
    import hmac
    import json

    _, sessions = catalog
    with sessions.begin() as db:
        db.add(PlanLimitORM(
            plan_code="business", revision=1,
            resource="ai.requests", scope="tenant",
            limit_units=100, window_seconds=86400,
        ))
    key = "synthetic-plan-only-service-key-32-bytes-long"
    request = {
        "tenant_id": "tenant-a", "unit_id": "unit-1",
        "capability": "atendimento_interpretacao",
        "challenge": "fresh-challenge-0123456789abcdef",
        "input_bound": 100, "output_bound": 50,
        "requested_at": int(NOW.timestamp()),
    }

    def invoke(payload, *, tamper=False):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(
            key.encode(),
            b"POST\n/internal/v1/assistant/core-plan-grant\n" + raw,
            hashlib.sha256,
        ).hexdigest()
        return authenticated_core_plan_grant(
            raw_body=raw + (b" " if tamper else b""),
            request_signature=signature, secret=key, sessions=sessions, now=NOW,
        )

    signed, signature = invoke(request)
    assert hmac.compare_digest(signature, hmac.new(
        key.encode(), b"/internal/v1/assistant/core-plan-grant\n" + signed,
        hashlib.sha256,
    ).hexdigest())
    assert json.loads(signed)["challenge"] == request["challenge"]
    with pytest.raises(PlanLimitDenied, match="grant_denied"):
        invoke(request, tamper=True)
    with pytest.raises(PlanLimitDenied, match="grant_denied"):
        invoke({**request, "requested_at": int(NOW.timestamp()) - 31})
    with sessions.begin() as db:
        db.get(TenantLicenseORM, "tenant-a").status = "suspended"
    with pytest.raises(PlanLimitDenied):
        invoke(request)
