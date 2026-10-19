"""Customer-facing consumption panel, with authenticated tenant isolation."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fm_assistant.db import PlanLimitORM, PlanVersionORM, TenantLicenseORM
from fm_assistant.plan_consumption_view import MeterReading, PlanConsumptionView


def _bootstrap(client, *, tenant_id="tenant-a", email="owner-a@example.com"):
    res = client.post(
        "/v1/bootstrap/tenant-owner",
        headers={"X-Admin-Key": "admin-test-key"},
        json={
            "tenant_id": tenant_id, "tenant_name": tenant_id,
            "unit_id": "unit-a", "unit_name": "Unidade A",
            "owner_email": email, "owner_name": "Owner",
            "password": "OwnerPassword!123",
            "plan_code": "trial", "trial_days": 14,
        },
    )
    assert res.status_code == 200, res.text


def _login(client, *, tenant_id="tenant-a", email="owner-a@example.com"):
    res = client.post("/v1/auth/login", json={
        "tenant_id": tenant_id, "email": email,
        "password": "OwnerPassword!123",
    })
    assert res.status_code == 200, res.text


NOW = datetime.now(UTC)


def _plan(client, tenant: str, *, revision: int, cap: int) -> None:
    engine = create_engine(client.app.state.settings.database_url)
    with Session(engine) as db, db.begin():
        db.add(PlanVersionORM(
            plan_code="trial", revision=revision,
            label=f"Franquia {revision}", status="published", created_at=NOW,
        ))
        for metric, units in (
            ("ai.requests", 100),
            ("ai.total_tokens", cap),
            ("ai.cost_usd_microunits", 1234567),
        ):
            db.add(PlanLimitORM(
                plan_code="trial", revision=revision,
                resource=metric, scope="tenant",
                limit_units=units, window_seconds=86400,
            ))
        lic = db.get(TenantLicenseORM, tenant)
        lic.plan_revision = revision
    engine.dispose()


def test_plan_dashboard_api_is_private_and_does_not_invent_usage(client):
    _bootstrap(client)
    response = client.get("/v1/plan/consumption")
    assert response.status_code == 401
    _plan(client, "tenant-a", revision=1, cap=500000)
    _login(client)
    result = client.get("/v1/plan/consumption")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["plan_name"] == "Franquia 1"
    assert body["all_features_included"] is True
    assert body["usage_verified"] is False
    assert {x["resource"] for x in body["consumption"]} == {
        "ai.requests", "ai.total_tokens",
    }
    assert all(x["status"] == "metering_unavailable" for x in body["consumption"])
    assert all(x["remaining_units"] is None for x in body["consumption"])
    assert "ai.cost_usd_microunits" not in result.text
    assert result.headers["cache-control"] == "no-store"
    html = client.get("/v1/plan/consumption/dashboard")
    assert html.status_code == 200
    assert "Franquia 1" in html.text
    assert "Saldo não verificado" in html.text
    assert "ai.cost_usd_microunits" not in html.text
    assert "<progress" not in html.text
    assert html.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in html.headers["content-security-policy"]


def test_foreign_tenant_scope_cannot_be_selected_by_query(client):
    _bootstrap(client, tenant_id="tenant-a", email="a@example.com")
    _bootstrap(client, tenant_id="tenant-b", email="b@example.com")
    _plan(client, "tenant-a", revision=1, cap=200)
    _plan(client, "tenant-b", revision=2, cap=900)
    _login(client, tenant_id="tenant-a", email="a@example.com")
    result = client.get("/v1/plan/consumption?tenant_id=tenant-b&unit_id=unit-b")
    assert result.status_code == 200
    assert result.json()["revision"] == 1
    assert result.json()["plan_name"] == "Franquia 1"
    assert "Franquia 2" not in result.text


def test_subscription_without_valid_revision_does_not_show_fake_balance(client):
    _bootstrap(client)
    _login(client)
    result = client.get("/v1/plan/consumption")
    assert result.status_code == 403
    assert result.json()["detail"] == "plan_unavailable"


def test_trusted_meter_snapshots_are_distinguished_from_unknown(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from fm_assistant.db import Base, TenantORM, UnitORM

    engine = create_engine(f"sqlite:///{tmp_path / 'meter.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(TenantORM(
            tenant_id="a", display_name="A", slug="a", status="active",
            created_at=NOW, updated_at=NOW,
        ))
        db.add(UnitORM(
            tenant_id="a", unit_id="u", display_name="U", status="active",
            created_at=NOW, updated_at=NOW,
        ))
        db.add(TenantLicenseORM(
            tenant_id="a", plan_code="trial", plan_revision=1, status="trial",
            trial_started_at=NOW, trial_ends_at=NOW + timedelta(days=1),
            period_started_at=None, period_ends_at=None,
            created_at=NOW, updated_at=NOW,
        ))
        db.add(PlanVersionORM(
            plan_code="trial", revision=1, label="Plan", status="published",
            created_at=NOW,
        ))
        for metric in ("ai.requests", "ai.total_tokens"):
            db.add(PlanLimitORM(
                plan_code="trial", revision=1, resource=metric, scope="tenant",
                limit_units=100, window_seconds=86400,
            ))

    class Reader:
        def read(self, *, tenant_id, unit_id, metric, scope, at, policy_revision,
                 limit_units, window_seconds):
            assert (tenant_id, unit_id, scope) == ("a", "u", "tenant")
            if metric == "ai.requests":
                return MeterReading(
                    consumed_units=12, reserved_units=8,
                    remaining_units=80, observed_at=NOW,
                    policy_revision=policy_revision, limit_units=limit_units,
                    window_seconds=window_seconds,
                )
            return None

    view = PlanConsumptionView(sessions, reader=Reader()).get(
        tenant_id="a", unit_id="u", now=NOW,
    )
    assert view["usage_verified"] is False
    req = next(x for x in view["consumption"] if x["resource"] == "ai.requests")
    token = next(x for x in view["consumption"] if x["resource"] == "ai.total_tokens")
    assert (req["consumed_units"], req["reserved_units"], req["remaining_units"]) == (
        12, 8, 80,
    )
    assert token["remaining_units"] is None
    engine.dispose()
