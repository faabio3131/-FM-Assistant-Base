"""Signed Assistant gateway: byte-exact HMAC and fail-closed HTTP behavior."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx
import pytest

from core.ai_assistant_credential_gateway import AssistantSignedCredentialGateway
from core.ai_service_settings import CoreEnvironment, CoreSettings
from core.ai_tenant_credential_resolver import TenantCredentialDenied

SIGNING_KEY = "only-synthetic-core-bridge-hmac-secret-000001"
URL = "https://assistant.example"


def test_scoped_gateway_signs_exact_request_and_uses_tls():
    seen = []

    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == URL + "/internal/v1/core/credentials/resolve"
        body = request.content
        payload = json.loads(body)
        assert payload == {
            "tenant_id": "tenant-a",
            "unit_id": "unit-a",
            "capability": "atendimento_interpretacao",
            "connection_id": "connection-a",
        }
        timestamp = request.headers["X-FM-Core-Timestamp"]
        nonce = request.headers["X-FM-Core-Nonce"]
        key_id = request.headers["X-FM-Core-Key-ID"]
        assert abs(int(timestamp) - int(datetime.now(UTC).timestamp())) <= 60
        assert key_id == "fm-core-v1"
        assert len(nonce) >= 22
        message = (
            "POST\\n/internal/v1/core/credentials/resolve\\n"
            + key_id + "\\n" + timestamp + "\\n" + nonce + "\\n"
            + hashlib.sha256(body).hexdigest()
        ).encode("ascii")
        signature = hmac.new(SIGNING_KEY.encode(), message, hashlib.sha256).hexdigest()
        assert hmac.compare_digest(signature, request.headers["X-FM-Core-Signature"])
        assert "synthetic-secret-value" not in body.decode()
        seen.append(nonce)
        return httpx.Response(200, json={"secret": "synthetic-secret-value"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = AssistantSignedCredentialGateway(
        base_url=URL, key_id="fm-core-v1", signing_key=SIGNING_KEY, client=client
    )
    result = gateway.resolve_scoped_secret(
        tenant_id="tenant-a",
        unit_id="unit-a",
        capability="atendimento_interpretacao",
        opaque_reference="connection-a",
    )
    assert result.reveal() == "synthetic-secret-value"
    assert "synthetic-secret-value" not in repr(result)
    assert len(seen) == 1
    client.close()


@pytest.mark.parametrize("status", [301, 302, 401, 403, 404, 409, 429, 500, 503])
def test_denied_or_redirected_response_never_exposes_secret_or_retries(status):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(status, json={"detail": "synthetic-sensitive-provider-token"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = AssistantSignedCredentialGateway(
        base_url=URL, key_id="fm-core-v1", signing_key=SIGNING_KEY, client=client
    )
    with pytest.raises(TenantCredentialDenied, match="byok_denied") as error:
        gateway.resolve_scoped_secret(
            tenant_id="tenant-a", unit_id="unit-a",
            capability="atendimento_interpretacao", opaque_reference="connection-a",
        )
    assert "synthetic-sensitive-provider-token" not in str(error.value)
    assert len(calls) == 1
    client.close()


def test_invalid_response_is_denied():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"secret": ""})
    ))
    gateway = AssistantSignedCredentialGateway(
        base_url=URL, key_id="fm-core-v1", signing_key=SIGNING_KEY, client=client
    )
    with pytest.raises(TenantCredentialDenied):
        gateway.resolve_scoped_secret(
            tenant_id="tenant-a", unit_id="unit-a",
            capability="atendimento_interpretacao", opaque_reference="connection-a",
        )
    client.close()


@pytest.mark.parametrize("base_url", [
    "http://assistant.example",
    "https://username:password@assistant.example",
    "https://assistant.example/admin",
    "https://assistant.example?tenant=tenant-a",
    "https://assistant.example#fragment",
])
def test_url_must_be_https_clean_origin(base_url):
    with pytest.raises(ValueError, match="https_origin_required"):
        AssistantSignedCredentialGateway(
            base_url=base_url, key_id="fm-core-v1", signing_key=SIGNING_KEY
        )


def test_unscoped_port_is_refused_even_with_valid_key():
    gateway = AssistantSignedCredentialGateway(
        base_url=URL, key_id="fm-core-v1", signing_key=SIGNING_KEY
    )
    with pytest.raises(TenantCredentialDenied, match="byok_scope_required"):
        gateway.resolve_active_secret(
            tenant_id="tenant-a", opaque_reference="connection-a"
        )


def test_configuration_rejects_partial_or_insecure_bridge():
    cfg = CoreSettings(
        environment=CoreEnvironment.TEST,
        service_key="core-test-service",
        routes=(),
        control_plane_database_url="sqlite:///temporary-test.db",
        assistant_bridge_url=URL,
    )
    with pytest.raises(RuntimeError, match="bridge_config_incomplete"):
        cfg.validate()
    with pytest.raises(RuntimeError, match="bridge_config_invalid"):
        CoreSettings(
            environment=CoreEnvironment.TEST,
            service_key="core-test-service",
            routes=(),
            control_plane_database_url="sqlite:///temporary-test.db",
            assistant_bridge_url="http://assistant.example",
            assistant_bridge_key_id="fm-core-v1",
            assistant_bridge_signing_key=SIGNING_KEY,
        ).validate()
