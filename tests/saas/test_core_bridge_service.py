"""Core bridge: signed service identity, grants, replay, revocation, audit.

Synthetic credentials only. No real provider call and no external network.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.api import create_app
from fm_assistant.command_bridge_control_models import CommandBridgeControlEventORM
from fm_assistant.command_bridge_control_service import sign_command_control
from fm_assistant.core_bridge_models import (
    CoreBridgeAccessORM,
    CoreBridgeGrantORM,
    CoreBridgeIdentityORM,
)
from fm_assistant.core_bridge_service import sign_core_bridge
from fm_assistant.credential_vault import FernetCredentialVault
from fm_assistant.db import (
    EntitlementORM,
    IntegrationCapabilityORM,
    IntegrationConnectionORM,
    IntegrationProviderORM,
    IntegrationSecretVersionORM,
    TenantLicenseORM,
    TenantORM,
    UnitORM,
)
from fm_assistant.settings import Environment, Settings

SIGNING_KEY = "only-synthetic-core-bridge-hmac-secret-000001"
COMMAND_KEY = "synthetic-command-control-signing-key-000002"
COMMAND_KEY_ID = "command-platform-key-v1"
PLATFORM_ORG_ID = "fm-company-organization"
KEY_ID = "fm-core-dev-v1"
PATH = "/internal/v1/core/credentials/resolve"
PAYLOAD = {
    "tenant_id": "tenant-a",
    "unit_id": "unit-a",
    "capability": "ai.text",
    "connection_id": "connection-a",
}


@pytest.fixture
def bridge_client(tmp_path):
    cfg = Settings(
        environment=Environment.TEST,
        database_url=f"sqlite:///{tmp_path / 'bridge.db'}",
        admin_key="test-admin",
        credential_pepper="test-credential-pepper-123",
        channel_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        session_pepper="test-session-pepper-of-sufficient-length",
        session_ttl_minutes=480,
        model_backend="development",
        model_base_url=None,
        model_api_key=None,
        model_name=None,
        core_base_url=None,
        core_service_key=None,
        auto_create_schema=True,
        core_bridge_key_id=KEY_ID,
        core_bridge_signing_key=SIGNING_KEY,
        command_control_key_id=COMMAND_KEY_ID,
        command_control_signing_key=COMMAND_KEY,
        trusted_command_organization_id=PLATFORM_ORG_ID,
    ).validate()
    app = create_app(cfg)
    with TestClient(app) as client:
        engine = create_engine(cfg.database_url)
        sessions = sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(UTC)
        vault = FernetCredentialVault(cfg.channel_encryption_key)
        with sessions.begin() as db:
            db.add(TenantORM(
                tenant_id="tenant-a", display_name="Tenant A", slug="tenant-a",
                status="active", created_at=now, updated_at=now,
            ))
            db.add(UnitORM(
                tenant_id="tenant-a", unit_id="unit-a", display_name="Unit A",
                status="active", created_at=now, updated_at=now,
            ))
            db.add(TenantLicenseORM(
                tenant_id="tenant-a", plan_code="pro", status="active",
                trial_started_at=None, trial_ends_at=None,
                period_started_at=now, period_ends_at=now + timedelta(days=30),
                created_at=now, updated_at=now,
            ))
            db.add(EntitlementORM(
                tenant_id="tenant-a", capability="ai.byok", enabled=True,
                limit_value=None, source="plan", updated_at=now,
            ))
            db.add(IntegrationProviderORM(
                provider_key="synthetic-ai", integration_type="ai",
                display_name="Synthetic Provider", definition_version=1,
                enabled=True, created_at=now, updated_at=now,
            ))
            db.add(IntegrationConnectionORM(
                connection_id="connection-a", tenant_id="tenant-a", unit_id="unit-a",
                provider_key="synthetic-ai", integration_type="ai",
                status="active", config_json="{}", revision=1,
                created_at=now, updated_at=now,
            ))
            db.add(IntegrationCapabilityORM(
                connection_id="connection-a", capability="ai.text",
            ))
            db.add(IntegrationSecretVersionORM(
                connection_id="connection-a", secret_name="api_key",
                version=1, source="tenant_managed", storage_backend="db_encrypted",
                ciphertext=vault.encrypt("synthetic-provider-secret-only"),
                secret_reference=None, active=True,
                expires_at=now + timedelta(days=1),
                revoked_at=None, created_at=now,
            ))
            db.add(CoreBridgeIdentityORM(
                key_id=KEY_ID, active=True, created_at=now, revoked_at=None,
            ))
            db.add(CoreBridgeGrantORM(
                key_id=KEY_ID, tenant_id="tenant-a", unit_id="unit-a",
                capability="ai.text", active=True, created_at=now, revoked_at=None,
            ))
        yield client, sessions
        engine.dispose()


def signed_request(payload=None, *, nonce=None, key=SIGNING_KEY, timestamp=None):
    data = json.dumps(
        PAYLOAD if payload is None else payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    timestamp = str(int(datetime.now(UTC).timestamp())) if timestamp is None else timestamp
    nonce = nonce or secrets.token_urlsafe(24)
    headers = {
        "X-FM-Core-Key-ID": KEY_ID,
        "X-FM-Core-Timestamp": timestamp,
        "X-FM-Core-Nonce": nonce,
        "X-FM-Core-Signature": sign_core_bridge(
            key=key, key_id=KEY_ID, timestamp=timestamp, nonce=nonce, body=data
        ),
        "Content-Type": "application/json",
    }
    return data, headers


def test_signed_identity_and_scoped_grant_release_without_cache(bridge_client):
    client, sessions = bridge_client
    data, headers = signed_request()
    response = client.post(PATH, content=data, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"secret": "synthetic-provider-secret-only"}
    assert response.headers["cache-control"] == "no-store"
    with sessions() as db:
        rows = db.scalars(select(CoreBridgeAccessORM)).all()
        assert len(rows) == 1
        assert rows[0].outcome == "released"
        assert rows[0].tenant_id == "tenant-a"
        assert rows[0].capability == "ai.text"


def test_replay_and_invalid_signature_are_denied(bridge_client):
    client, sessions = bridge_client
    data, headers = signed_request()
    assert client.post(PATH, content=data, headers=headers).status_code == 200
    assert client.post(PATH, content=data, headers=headers).status_code == 401
    invalid = signed_request(key="unauthorized-test-key-1234567890123456")
    assert client.post(PATH, content=invalid[0], headers=invalid[1]).status_code == 401
    with sessions() as db:
        assert len(db.scalars(select(CoreBridgeAccessORM)).all()) == 1


def test_expired_signature_or_missing_identity_is_denied(bridge_client):
    client, _ = bridge_client
    expired = signed_request(timestamp=str(int(datetime.now(UTC).timestamp()) - 120))
    assert client.post(PATH, content=expired[0], headers=expired[1]).status_code == 401
    assert client.post(PATH, json=PAYLOAD).status_code == 401


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "tenant-b"),
    ("unit_id", "unit-b"),
    ("capability", "ai.audio"),
    ("connection_id", "connection-b"),
])
def test_signed_cross_scope_request_is_denied_and_audited(bridge_client, field, value):
    client, sessions = bridge_client
    payload = dict(PAYLOAD)
    payload[field] = value
    data, headers = signed_request(payload)
    response = client.post(PATH, content=data, headers=headers)
    assert response.status_code == 401
    assert "synthetic-provider-secret-only" not in response.text
    with sessions() as db:
        rows = db.scalars(select(CoreBridgeAccessORM)).all()
        assert len(rows) == 1
        assert rows[0].outcome == "denied"


@pytest.mark.parametrize("model,pk,field,value", [
    (CoreBridgeIdentityORM, KEY_ID, "active", False),
    (CoreBridgeGrantORM, (KEY_ID, "tenant-a", "unit-a", "ai.text"), "active", False),
    (EntitlementORM, ("tenant-a", "ai.byok"), "enabled", False),
    (IntegrationConnectionORM, "connection-a", "status", "revoked"),
    (IntegrationSecretVersionORM, ("connection-a", "api_key", 1), "active", False),
    (IntegrationSecretVersionORM, ("connection-a", "api_key", 1), "revoked_at", datetime.now(UTC)),
])
def test_revocation_is_enforced_on_next_signed_request(bridge_client, model, pk, field, value):
    client, sessions = bridge_client
    with sessions.begin() as db:
        setattr(db.get(model, pk), field, value)
    data, headers = signed_request()
    assert client.post(PATH, content=data, headers=headers).status_code == 401


def test_secret_rotation_uses_only_latest_active_version(bridge_client):
    client, sessions = bridge_client
    now = datetime.now(UTC)
    with sessions.begin() as db:
        old = db.get(IntegrationSecretVersionORM, ("connection-a", "api_key", 1))
        old.active = False
        db.add(IntegrationSecretVersionORM(
            connection_id="connection-a", secret_name="api_key", version=2,
            source="tenant_managed", storage_backend="db_encrypted",
            ciphertext=FernetCredentialVault(
                client.app.state.settings.channel_encryption_key
            ).encrypt("rotated-synthetic-secret"),
            secret_reference=None, active=True,
            expires_at=now + timedelta(days=1), revoked_at=None, created_at=now,
        ))
    data, headers = signed_request()
    response = client.post(PATH, content=data, headers=headers)
    assert response.status_code == 200
    assert response.json()["secret"] == "rotated-synthetic-secret"


def test_bridge_without_configuration_fails_closed(client):
    response = client.post(PATH, json=PAYLOAD)
    assert response.status_code == 401



def test_signed_core_gateway_end_to_end(bridge_client):
    """Wire the REAL Core HTTP signer into the REAL Assistant ASGI endpoint."""
    import httpx

    module = pytest.importorskip("core.ai_assistant_credential_gateway")
    from core.ai_tenant_credential_resolver import TenantCredentialDenied

    assistant, sessions = bridge_client

    def forward(request):
        response = assistant.post(
            PATH, content=request.content, headers=dict(request.headers)
        )
        return httpx.Response(
            status_code=response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )

    transport = httpx.Client(transport=httpx.MockTransport(forward))
    try:
        gateway = module.AssistantSignedCredentialGateway(
            base_url="https://assistant.example",
            key_id=KEY_ID,
            signing_key=SIGNING_KEY,
            client=transport,
        )
        secret = gateway.resolve_scoped_secret(
            tenant_id="tenant-a",
            unit_id="unit-a",
            capability="ai.text",
            opaque_reference="connection-a",
        )
        assert secret.reveal() == "synthetic-provider-secret-only"

        # Same gateway and key must stop immediately after grant revocation.
        with sessions.begin() as db:
            grant = db.get(
                CoreBridgeGrantORM, (KEY_ID, "tenant-a", "unit-a", "ai.text")
            )
            grant.active = False
            grant.revoked_at = datetime.now(UTC)
        with pytest.raises(TenantCredentialDenied):
            gateway.resolve_scoped_secret(
                tenant_id="tenant-a",
                unit_id="unit-a",
                capability="ai.text",
                opaque_reference="connection-a",
            )

        with sessions() as db:
            rows = db.scalars(select(CoreBridgeAccessORM)).all()
            assert len(rows) == 2
            assert {row.outcome for row in rows} == {"released", "denied"}
            assert len({row.nonce for row in rows}) == 2
    finally:
        transport.close()


COMMAND_PATH = "/internal/v1/command/core-bridge/manage"


def command_request(
    action: str, *, nonce: str | None = None, key: str = COMMAND_KEY,
    organization: str = PLATFORM_ORG_ID, timestamp: str | None = None,
):
    payload = {
        "action": action,
        "tenant_id": "tenant-a",
        "unit_id": "unit-a",
        "capability": "ai.text",
        "target_key_id": KEY_ID,
        "actor_user_id": "fm-human-admin-1",
        "organization_id": organization,
        "step_up_at": int(datetime.now(UTC).timestamp()),
        "command_request_id": secrets.token_urlsafe(24),
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    timestamp = timestamp or str(int(datetime.now(UTC).timestamp()))
    nonce = nonce or secrets.token_urlsafe(24)
    headers = {
        "X-FM-Command-Key-ID": COMMAND_KEY_ID,
        "X-FM-Command-Timestamp": timestamp,
        "X-FM-Command-Nonce": nonce,
        "X-FM-Command-Signature": sign_command_control(
            key=key, key_id=COMMAND_KEY_ID,
            timestamp=timestamp, nonce=nonce, body=body,
        ),
    }
    return body, headers


def test_command_revokes_grant_and_denies_next_core_call(bridge_client):
    client, sessions = bridge_client
    data, headers = command_request("revoke_grant")
    response = client.post(COMMAND_PATH, content=data, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "revoked"}
    core_body, core_headers = signed_request()
    assert client.post(PATH, content=core_body, headers=core_headers).status_code == 401
    with sessions() as db:
        grant = db.get(CoreBridgeGrantORM, (KEY_ID, "tenant-a", "unit-a", "ai.text"))
        assert not grant.active and grant.revoked_at is not None
        events = db.scalars(select(CommandBridgeControlEventORM)).all()
        assert len(events) == 1 and events[0].outcome == "revoked"
        assert events[0].actor_user_id == "fm-human-admin-1"


def test_command_revokes_identity_and_all_grants(bridge_client):
    client, sessions = bridge_client
    data, headers = command_request("revoke_identity")
    response = client.post(COMMAND_PATH, content=data, headers=headers)
    assert response.status_code == 200
    with sessions() as db:
        identity = db.get(CoreBridgeIdentityORM, KEY_ID)
        assert not identity.active and identity.revoked_at is not None
        assert not db.get(
            CoreBridgeGrantORM, (KEY_ID, "tenant-a", "unit-a", "ai.text")
        ).active
    core_body, core_headers = signed_request()
    assert client.post(PATH, content=core_body, headers=core_headers).status_code == 401
    data, headers = command_request("provision")
    assert client.post(COMMAND_PATH, content=data, headers=headers).status_code == 401


def test_command_provision_then_grant_scoped_identity(bridge_client):
    client, sessions = bridge_client
    with sessions.begin() as db:
        db.delete(db.get(CoreBridgeGrantORM, (KEY_ID, "tenant-a", "unit-a", "ai.text")))
        db.delete(db.get(CoreBridgeIdentityORM, KEY_ID))
    data, headers = command_request("provision")
    response = client.post(COMMAND_PATH, content=data, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "provisioned"}
    core_body, core_headers = signed_request()
    assert client.post(PATH, content=core_body, headers=core_headers).status_code == 401
    data, headers = command_request("grant")
    response = client.post(COMMAND_PATH, content=data, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "granted"}
    core_body, core_headers = signed_request()
    assert client.post(PATH, content=core_body, headers=core_headers).status_code == 200


def test_command_rejects_cross_org_bad_signature_and_expiry(bridge_client):
    client, sessions = bridge_client
    for kwargs in (
        {"organization": "another-company"},
        {"key": "wrong-command-control-hmac-key-1234567"},
        {"timestamp": str(int(datetime.now(UTC).timestamp()) - 120)},
    ):
        data, headers = command_request("revoke_grant", **kwargs)
        assert client.post(COMMAND_PATH, content=data, headers=headers).status_code == 401
    with sessions() as db:
        assert db.scalars(select(CommandBridgeControlEventORM)).all() == []
        assert db.get(
            CoreBridgeGrantORM, (KEY_ID, "tenant-a", "unit-a", "ai.text")
        ).active


def test_command_replay_does_not_repeat_mutation(bridge_client):
    client, sessions = bridge_client
    data, headers = command_request("revoke_grant")
    assert client.post(COMMAND_PATH, content=data, headers=headers).status_code == 200
    assert client.post(COMMAND_PATH, content=data, headers=headers).status_code == 401
    with sessions() as db:
        assert len(db.scalars(select(CommandBridgeControlEventORM)).all()) == 1


def test_command_control_missing_configuration_is_denied(client):
    data, headers = command_request("provision")
    response = client.post(COMMAND_PATH, content=data, headers=headers)
    assert response.status_code == 401



def test_command_hmac_contract_matches_node_crypto_reference_vector():
    raw_body = b'{"action":"revoke_grant","tenant_id":"tenant-a"}'
    digest = sign_command_control(
        key=COMMAND_KEY,
        key_id=COMMAND_KEY_ID,
        timestamp="1792335600",
        nonce="nonce-123456789012345678901234",
        body=raw_body,
    )
    assert digest == (
        "954f3ac7be0e0f854ac5c96e8097f69be2cd347ef72d1ce545bc7ec833abd78b"
    )


def test_command_rejects_forged_target_identity(bridge_client):
    client, sessions = bridge_client
    body, headers = command_request("revoke_identity")
    parsed = json.loads(body)
    parsed["target_key_id"] = "unauthorized-core-key"
    tampered = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    headers["X-FM-Command-Signature"] = sign_command_control(
        key=COMMAND_KEY, key_id=COMMAND_KEY_ID,
        timestamp=headers["X-FM-Command-Timestamp"],
        nonce=headers["X-FM-Command-Nonce"], body=tampered,
    )
    assert client.post(COMMAND_PATH, content=tampered, headers=headers).status_code == 401
    with sessions() as db:
        assert db.get(CoreBridgeIdentityORM, KEY_ID).active


def test_command_rejects_old_step_up_even_with_valid_hmac(bridge_client):
    client, sessions = bridge_client
    body, headers = command_request("revoke_identity")
    parsed = json.loads(body)
    parsed["step_up_at"] = int(datetime.now(UTC).timestamp()) - 360
    tampered = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    headers["X-FM-Command-Signature"] = sign_command_control(
        key=COMMAND_KEY, key_id=COMMAND_KEY_ID,
        timestamp=headers["X-FM-Command-Timestamp"],
        nonce=headers["X-FM-Command-Nonce"], body=tampered,
    )
    assert client.post(COMMAND_PATH, content=tampered, headers=headers).status_code == 401
    with sessions() as db:
        assert db.get(CoreBridgeIdentityORM, KEY_ID).active
