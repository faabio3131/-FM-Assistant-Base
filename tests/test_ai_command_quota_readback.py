"""FM Command F3 readback: actual Core sqlite policy and no artificial reservations."""
from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_command_quota_readback import (
    PATH, SCHEMA, command_core_quota_readback_router, sign_command_quota_readback,
)
from core.ai_control_plane import ControlPlaneBase
from core.ai_plan_usage_guard import PlanQuotaPolicy
from core.ai_quota_store import QuotaDenied, QuotaRequirement, QuotaReservations

SECRET = b"synthetic-command-core-quota-readback-key-123456"


class FreshAuthority:
    def __init__(self):
        self.active = True
        self.fail = False
        self.reads = 0

    def resolve(self, *, tenant_id, unit_id, capability, now):
        self.reads += 1
        if self.fail or not self.active or tenant_id != "tenant-a" or unit_id != "unit-a":
            raise QuotaDenied("synthetic_license_denied")
        if capability not in {"atendimento_interpretacao", "atendimento_transcricao"}:
            raise QuotaDenied("synthetic_capability_denied")
        return PlanQuotaPolicy(
            tenant_id=tenant_id, unit_id=unit_id, plan_code="BASE", revision=1,
            valid_until=now + timedelta(seconds=35),
            input_bound=20, output_bound=20,
            scopes=(("ai.requests", "tenant"), ("ai.total_tokens", "tenant")),
            grants=(
                ("ai.requests", "tenant", 10, 86400),
                ("ai.total_tokens", "tenant", 500, 86400),
            ),
        )


def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'core-readback.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    quota = QuotaReservations(sessionmaker(bind=engine, expire_on_commit=False))
    authority = FreshAuthority()
    app = FastAPI()
    app.include_router(command_core_quota_readback_router(
        authority=authority, quota=quota, shared_secret=SECRET,
    ))
    client = TestClient(app)
    return engine, quota, authority, client


def body(**values):
    result = {
        "schema": SCHEMA, "tenant_id": "tenant-a", "unit_id": "unit-a",
        "capability": "atendimento_interpretacao",
        "issued_at": int(datetime.now(UTC).timestamp()),
        "nonce": secrets.token_urlsafe(24),
    }
    result.update(values)
    return result


def call(client, data, *, signing_key=SECRET):
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    signature = sign_command_quota_readback(secret=signing_key, body=raw)
    return client.post(PATH, content=raw, headers={
        "Content-Type": "application/json",
        "X-FM-Command-Quota-Signature": signature,
    })


def test_fresh_active_license_and_existing_ledger_are_read_without_reservation(tmp_path):
    engine, quota, authority, client = setup(tmp_path)
    try:
        before = call(client, body())
        assert before.status_code == 409
        assert before.json()["detail"] == "core_quota_readback.policy_not_projected"
        quota.project_signed_grants(
            tenant_id="tenant-a", unit_id="unit-a", revision=1,
            grants=(("ai.requests", "tenant", 10, 86400),
                    ("ai.total_tokens", "tenant", 500, 86400)),
        )
        quota.reserve_bundle(
            needs=(
                QuotaRequirement(tenant_id="tenant-a", unit_id="__tenant__",
                                 capability="ai.requests", units=1, policy_revision=1),
                QuotaRequirement(tenant_id="tenant-a", unit_id="__tenant__",
                                 capability="ai.total_tokens", units=40, policy_revision=1),
            ),
            request_id="synthetic-text-before-suspension", at=datetime.now(UTC),
        )
        good = call(client, body())
        assert good.status_code == 200, good.text
        result = good.json()
        assert good.headers["cache-control"] == "no-store"
        assert result["license_freshly_verified"] is True
        assert result["core_policy_matches_signed_grant"] is True
        assert result["reservation_created"] is False
        assert result["provider_called"] is False
        assert result["case_resolved"] is False
        assert {x["metric"]: x["reserved_units"] for x in result["quota_metrics"]} == {
            "ai.requests": 1, "ai.total_tokens": 40,
        }
        # A second read must not alter any quota counter.
        second = call(client, body(capability="atendimento_transcricao"))
        assert second.status_code == 200
        assert second.json()["quota_metrics"] == result["quota_metrics"]
        assert authority.reads == 3
        quota_usage = quota.usage_snapshot(
            tenant_id="tenant-a", unit_id="__tenant__",
            capability="ai.total_tokens", at=datetime.now(UTC),
        )
        assert quota_usage.reserved_units == 40
    finally:
        engine.dispose()


def test_suspension_and_assistant_outage_are_not_reported_as_active(tmp_path):
    engine, quota, authority, client = setup(tmp_path)
    try:
        quota.project_signed_grants(tenant_id="tenant-a", unit_id="unit-a",
                                    revision=1, grants=(
            ("ai.requests", "tenant", 10, 86400),
            ("ai.total_tokens", "tenant", 500, 86400),
        ))
        authority.active = False
        assert call(client, body()).status_code == 409
        authority.active = True
        authority.fail = True
        assert call(client, body()).status_code == 409
        authority.fail = False
        assert call(client, body(tenant_id="tenant-b")).status_code == 409
        assert call(client, body(unit_id="foreign-unit")).status_code == 409
    finally:
        engine.dispose()


def test_invalid_or_tampered_hmac_rejected_before_policy_read(tmp_path):
    engine, _, authority, client = setup(tmp_path)
    try:
        payload = body()
        raw = json.dumps(payload).encode()
        assert client.post(PATH, content=raw, headers={
            "Content-Type": "application/json",
        }).status_code == 401
        previous = sign_command_quota_readback(secret=SECRET, body=raw)
        altered = json.dumps({**payload, "tenant_id": "foreign-tenant"}).encode()
        assert client.post(PATH, content=altered, headers={
            "Content-Type": "application/json",
            "X-FM-Command-Quota-Signature": previous,
        }).status_code == 401
        assert authority.reads == 0
    finally:
        engine.dispose()


def test_schema_clock_duplication_and_payload_size_fail_closed(tmp_path):
    engine, _, authority, client = setup(tmp_path)
    try:
        for case in (
            body(schema="wrong"),
            body(issued_at=True),
            body(issued_at=int(datetime.now(UTC).timestamp()) - 60),
            body(nonce="weak"),
            body(capability="provider_admin"),
            body(tenant_id="../../tenant"),
            body(unit_id=""),
            body(extra=True),
        ):
            assert call(client, case).status_code == 400
        raw = json.dumps(body()).encode()
        duplicate = raw[:-1] + b',"tenant_id":"tenant-x"}'
        assert client.post(PATH, content=duplicate, headers={
            "Content-Type": "application/json",
            "X-FM-Command-Quota-Signature": sign_command_quota_readback(
                secret=SECRET, body=duplicate,
            ),
        }).status_code == 400
        assert client.post(PATH, content=b"x" * 2100, headers={
            "Content-Type": "application/json",
        }).status_code == 413
        assert authority.reads == 0
    finally:
        engine.dispose()


def test_mismatched_or_revised_policy_never_claims_core_alignment(tmp_path):
    engine, quota, authority, client = setup(tmp_path)
    try:
        quota.project_signed_grants(tenant_id="tenant-a", unit_id="unit-a",
                                    revision=1, grants=(
            ("ai.requests", "tenant", 20, 86400),
            ("ai.total_tokens", "tenant", 500, 86400),
        ))
        result = call(client, body())
        assert result.status_code == 409
        assert result.json()["detail"] == "core_quota_readback.policy_mismatch"
    finally:
        engine.dispose()
