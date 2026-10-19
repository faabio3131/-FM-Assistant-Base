"""Read-only quota dashboard endpoint requires Core service authentication."""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.ai_control_plane import ControlPlaneBase
from core.ai_quota_store import AIQuotaPolicyRecord, AIQuotaReservationRecord, ReservationState
from core.ai_service_api import create_app
from tests.service.test_ai_service_api import FakeRuntime, _settings


def test_core_plan_read_denies_anonymous_and_unavailable_ledger(tmp_path):
    app = create_app(_settings(), runtime=FakeRuntime())
    params = dict(
        tenant_id="tenant-a", unit_id="unit-a",
        resource="ai.total_tokens", scope="tenant",
    )
    with TestClient(app) as client:
        assert client.get("/v1/plan/usage", params=params).status_code == 401
        denied = client.get(
            "/v1/plan/usage", params=params,
            headers={"X-Core-Service-Key": "core-test-key"},
        )
        assert denied.status_code == 503
        assert denied.json()["detail"] == "plan_usage_unavailable"


def test_core_plan_read_returns_only_requested_scope_and_real_ledger_balance(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'core-quota-read.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    now = datetime.now(UTC)
    period = int(now.timestamp()) // 86400
    with Session(engine) as db, db.begin():
        db.add(AIQuotaPolicyRecord(
            tenant_id="tenant-a", unit_id="__tenant__",
            capability="ai.total_tokens", limit_units=1000,
            window_seconds=86400, revision=3,
        ))
        db.add(AIQuotaReservationRecord(
            tenant_id="tenant-a", unit_id="__tenant__",
            capability="ai.total_tokens", request_id="req-used",
            period=period, policy_revision=3,
            reserved_units=200, consumed_units=150,
            state=ReservationState.SETTLED, created_at=now,
        ))
        db.add(AIQuotaReservationRecord(
            tenant_id="tenant-a", unit_id="__tenant__",
            capability="ai.total_tokens", request_id="req-pending",
            period=period, policy_revision=3,
            reserved_units=100, consumed_units=0,
            state=ReservationState.RESERVED, created_at=now,
        ))
    app = create_app(_settings(), runtime=FakeRuntime())
    with TestClient(app) as client:
        app.state.control_plane_engine = engine
        params = dict(
            tenant_id="tenant-a", unit_id="unit-a",
            resource="ai.total_tokens", scope="tenant",
        )
        res = client.get(
            "/v1/plan/usage", params=params,
            headers={"X-Core-Service-Key": "core-test-key"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["limit_units"] == 1000
        assert res.json()["consumed_units"] == 150
        assert res.json()["reserved_units"] == 100
        assert res.json()["remaining_units"] == 750
        assert res.json()["policy_revision"] == 3
        assert res.json()["scope"] == "tenant"
        foreign = client.get(
            "/v1/plan/usage",
            params={**params, "tenant_id": "tenant-b"},
            headers={"X-Core-Service-Key": "core-test-key"},
        )
        assert foreign.status_code == 503
        assert "750" not in foreign.text
    engine.dispose()
