"""Internal route is opt-in and never trusts a caller-supplied receipt."""
from datetime import UTC, datetime
from decimal import Decimal

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.ai_command_authority import CommandTrustPolicy
from core.ai_governed_recovery_api import governed_recovery_router
from core.ai_verified_usage_receipt import VerifiedProviderUsageReceipt


class StubEvidence:
    def verify(self, *, evidence_id, request_id, tenant_id, unit_id):
        return VerifiedProviderUsageReceipt(
            provider="gemini", model="m", request_id=request_id,
            tenant_id=tenant_id, unit_id=unit_id,
            input_tokens=8, output_tokens=2,
            provider_cost_usd=Decimal("0.001"),
            evidence_digest="d" * 64,
        )


class StubLedger:
    def __init__(self):
        self.calls = 0

    def reconcile_verified_provider_receipt(self, **kwargs):
        self.calls += 1
        assert kwargs["receipt"].input_tokens == 8


def test_recovery_route_requires_signed_human_and_verified_receipt():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    trust = CommandTrustPolicy(
        issuer="fm-command", audience="fm-core-recovery", public_key_pem=public,
    )
    ledger = StubLedger()
    app = FastAPI()
    app.include_router(governed_recovery_router(
        trust=trust, evidence=StubEvidence(), ledger=ledger,
    ))
    http = TestClient(app)
    path = "/internal/v1/command/ai/usage/reconcile"
    body = {
        "tenant_id": "tenant-1", "unit_id": "unit-1",
        "request_id": "request-1", "evidence_id": "provider-reference",
        "requests_revision": 1, "tokens_revision": 1,
    }
    assert http.post(path, json=body).status_code == 401
    assert ledger.calls == 0
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": "fm-command", "aud": "fm-core-recovery",
        "sub": "human-1", "jti": "signed-command-request-jti-1",
        "session_id": "admin-session-1", "iat": now, "nbf": now,
        "exp": now + 120, "step_up_at": now,
        "actor_type": "human", "role": "platform_admin",
        "scope": "fm_core_platform", "permissions": ["core.ai.admin.mutate"],
    }
    claims["role"] = "tenant_owner"
    invalid_token = jwt.encode(claims, private, algorithm="RS256")
    assert http.post(
        path, json=body, headers={"Authorization": "Bearer " + invalid_token},
    ).status_code == 403
    assert ledger.calls == 0
    claims["role"] = "platform_admin"
    valid_token = jwt.encode(claims, private, algorithm="RS256")
    assert http.post(
        path, json=body, headers={"Authorization": "Bearer " + valid_token},
    ).status_code == 204
    assert ledger.calls == 1


def test_default_core_app_does_not_mount_unverified_recovery_route():
    from core.ai_router import CapabilityIA
    from core.ai_service_api import create_app
    from core.ai_service_settings import CoreEnvironment, CoreSettings, ProviderRouteSettings

    cfg = CoreSettings(
        environment=CoreEnvironment.TEST,
        service_key="test-secret",
        routes=(ProviderRouteSettings(
            configuration_id="test", provider="stub", model="mock",
            capability=CapabilityIA.ATENDIMENTO_INTERPRETACAO,
            priority=1, price_snapshot_id="price-stub",
            adapter="gemini", base_url="https://test.example",
            api_key="fake",
        ),),
    )
    app = create_app(settings=cfg)
    assert not any(
        getattr(route, "path", "") == "/internal/v1/command/ai/usage/reconcile"
        for route in app.routes
    )


def test_opt_in_recovery_config_fails_closed_for_partial_or_weak_trust(tmp_path):
    """Invalid/half-enabled recovery must never mount a financial mutation."""
    from dataclasses import replace

    import pytest

    from core.ai_service_settings import CoreEnvironment, CoreSettings

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    baseline = CoreSettings(
        environment=CoreEnvironment.TEST, service_key="service-test-key",
        routes=(), control_plane_database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        governed_recovery_enabled=True,
        governed_recovery_issuer="fm-command",
        governed_recovery_audience="fm-core-recovery",
        governed_recovery_public_key_pem=public,
        governed_recovery_gateway_secret="FM-test-only-gateway-secret-long-enough-123",
        governed_recovery_source_id="fm-verified-gateway",
    )
    assert baseline.validate().governed_recovery_enabled
    for changed in (
        {"governed_recovery_enabled": False},
        {"governed_recovery_issuer": None},
        {"governed_recovery_public_key_pem": "forged-key"},
        {"governed_recovery_gateway_secret": "too-short"},
        {"governed_recovery_gateway_secret": baseline.service_key},
        {"governed_recovery_source_id": "wrong source"},
        {"control_plane_database_url": None},
    ):
        with pytest.raises(RuntimeError, match="core_recovery_"):
            replace(baseline, **changed).validate()


def test_opt_in_recovery_uses_only_immutable_scoped_evidence(tmp_path):
    """Real Core ASGI + migrated SQL quota ledger; all secrets synthetic."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from core.ai_provider_evidence_store import (
        TrustedProviderEvidenceStore,
        sign_verified_gateway_attestation,
    )
    from core.ai_quota_store import (
        AIQuotaPolicyRecord,
        AIQuotaReservationRecord,
        QuotaRequirement,
        QuotaReservations,
        ReservationState,
    )
    from core.ai_service_api import create_app
    from core.ai_service_settings import CoreEnvironment, CoreSettings
    from tests.service.test_ai_control_plane_bootstrap import migrated_db

    url, _, _ = migrated_db(tmp_path)
    engine = create_engine(url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    needs = (
        QuotaRequirement(tenant_id="tenant-1", unit_id="__tenant__",
                         capability="ai.requests", units=1, policy_revision=1),
        QuotaRequirement(tenant_id="tenant-1", unit_id="__tenant__",
                         capability="ai.total_tokens", units=100, policy_revision=1),
    )
    with sessions.begin() as db:
        for need in needs:
            db.add(AIQuotaPolicyRecord(
                tenant_id=need.tenant_id, unit_id=need.unit_id,
                capability=need.capability, limit_units=200,
                window_seconds=3600, revision=1,
            ))
    ledger = QuotaReservations(sessions)
    ledger.reserve_bundle(needs=needs, request_id="request-1", at=now)

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    source = "fm-verified-gateway"
    secret = b"synthetic-independent-evidence-key-123456"
    evidence = TrustedProviderEvidenceStore(
        sessions, gateway_secret=secret, source_id=source,
    )
    receipt = VerifiedProviderUsageReceipt(
        provider="gemini", model="example", request_id="request-1",
        tenant_id="tenant-1", unit_id="unit-1", input_tokens=8, output_tokens=2,
        provider_cost_usd=Decimal("0.001"), evidence_digest="f" * 64,
    )
    # The test explicitly simulates the independently trusted source. It is
    # NOT proof of live Gemini/OpenAI attestations or real provider verification.
    signature = sign_verified_gateway_attestation(
        evidence_id="evidence-1", source_id=source, receipt=receipt,
        secret=secret,
    )
    assert evidence.record_attested(
        evidence_id="evidence-1", receipt=receipt, gateway_signature=signature,
    )
    settings = CoreSettings(
        environment=CoreEnvironment.TEST, service_key="service-test-key",
        routes=(), control_plane_database_url=url,
        governed_recovery_enabled=True, governed_recovery_issuer="fm-command",
        governed_recovery_audience="fm-core-recovery",
        governed_recovery_public_key_pem=public,
        governed_recovery_gateway_secret=secret.decode(),
        governed_recovery_source_id=source,
    )
    app = create_app(settings=settings)
    path = "/internal/v1/command/ai/usage/reconcile"
    assert any(getattr(route, "path", "") == path for route in app.routes)
    body = {
        "tenant_id": "tenant-1", "unit_id": "unit-1",
        "request_id": "request-1", "evidence_id": "evidence-1",
        "requests_revision": 1, "tokens_revision": 1,
    }
    issued = int(now.timestamp())
    claims = {
        "iss": "fm-command", "aud": "fm-core-recovery",
        "sub": "human-fm", "jti": "recovery-unique-command-jti-1",
        "session_id": "human-session", "iat": issued, "nbf": issued,
        "exp": issued + 120, "step_up_at": issued,
        "actor_type": "human", "role": "platform_admin",
        "scope": "fm_core_platform", "permissions": ["core.ai.admin.mutate"],
    }
    token = jwt.encode(claims, private, algorithm="RS256")
    with TestClient(app) as client:
        assert client.post(path, json=body).status_code == 401
        assert client.post(path, json={**body, "evidence_id": "wrong-id"},
                           headers={"Authorization": "Bearer " + token}).status_code == 409
        assert client.post(path, json={**body, "tenant_id": "other-tenant"},
                           headers={"Authorization": "Bearer " + token}).status_code == 409
        assert client.post(path, json=body,
                           headers={"Authorization": "Bearer " + token}).status_code == 204
        # A second request cannot settle the same reserved bundle, even with
        # the same valid evidence.
        assert client.post(path, json=body,
                           headers={"Authorization": "Bearer " + token}).status_code == 409

    with sessions() as db:
        rows = db.scalars(select(AIQuotaReservationRecord).where(
            AIQuotaReservationRecord.tenant_id == "tenant-1",
            AIQuotaReservationRecord.request_id == "request-1",
        )).all()
        assert len(rows) == 2
        assert all(row.state == ReservationState.SETTLED for row in rows)
        assert {r.capability: r.consumed_units for r in rows} == {
            "ai.requests": 1, "ai.total_tokens": 10,
        }
    engine.dispose()
