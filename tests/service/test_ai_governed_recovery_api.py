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
    from core.ai_service_api import create_app
    from core.ai_service_settings import CoreEnvironment, CoreSettings
    from core.ai_router import CapabilityIA
    from core.ai_service_settings import ProviderRouteSettings

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
