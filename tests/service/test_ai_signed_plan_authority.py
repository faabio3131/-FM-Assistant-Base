"""Contract security tests for signed Assistant policy assertions."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx
import pytest

from core.ai_quota_store import QuotaDenied
from core.ai_signed_plan_authority import (
    AssistantPlanHTTPSFetch,
    SignedAssistantPlanAuthority,
    signed_plan_body,
)

NOW = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)
SECRET = b"assistant-to-core-test-secret-key-32-bytes-12345"


def assertion(*, challenge="test-challenge-0123456789abcdef", **updates):
    obj = {
        "tenant_id": "tenant-a", "unit_id": "u1",
        "capability": "atendimento_interpretacao", "challenge": challenge,
        "plan_code": "all", "revision": 3,
        "expires_at": int(NOW.timestamp()) + 30,
        "licensed_until": int(NOW.timestamp()) + 86400,
        "input_bound": 100, "output_bound": 50,
        "scopes": [["ai.requests", "tenant"], ["ai.total_tokens", "tenant"]],
    }
    obj.update(updates)
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return raw, signed_plan_body(secret=SECRET, body=raw)


def resolve(*, grant=None, tenant="tenant-a", fetch=None):
    payload = grant
    authority = SignedAssistantPlanAuthority(
        secret=SECRET,
        fetch=fetch or (lambda t, u, c, ch: payload if payload is not None else assertion(challenge=ch)),
    )
    return authority.resolve(
        tenant_id=tenant, unit_id="u1",
        capability="atendimento_interpretacao", now=NOW,
    )


def test_valid_signed_grant_is_scoped_and_bounded():
    p = resolve()
    assert p.revision == 3
    assert p.valid_until.timestamp() == NOW.timestamp() + 30
    assert p.scopes == (("ai.requests", "tenant"), ("ai.total_tokens", "tenant"))


@pytest.mark.parametrize("grant", [
    assertion(tenant_id="tenant-b"),
    assertion(unit_id="u2"),
    assertion(revision=True),
    assertion(expires_at=int(NOW.timestamp()) + 61),
    assertion(expires_at=int(NOW.timestamp()) - 1),
    assertion(licensed_until=int(NOW.timestamp()) - 1),
    assertion(scopes=[["ai.requests", "tenant"], ["ai.total_tokens", "evil"]]),
])
def test_invalid_grants_fail_closed(grant):
    with pytest.raises(QuotaDenied):
        resolve(grant=grant)


def test_tampered_body_or_signature_is_denied():
    raw, signature = assertion()
    with pytest.raises(QuotaDenied, match="signature_invalid"):
        resolve(grant=(raw.replace(b"tenant-a", b"tenant-b"), signature))
    with pytest.raises(QuotaDenied, match="signature_invalid"):
        resolve(grant=(raw, "0" * 64))


def test_revocation_and_assistant_outage_are_checked_per_request():
    calls = [True]
    def fetch(_tenant, _unit, _cap, challenge):
        if calls:
            calls.pop()
            return assertion(challenge=challenge)
        raise OSError("assistant unreachable")

    resolve(fetch=fetch)
    with pytest.raises(QuotaDenied, match="grant_unavailable"):
        resolve(fetch=fetch)


def test_replayed_signed_grant_from_previous_request_is_denied():
    captured = None

    def fetch(_tenant, _unit, _cap, challenge):
        nonlocal captured
        if captured is None:
            captured = assertion(challenge=challenge)
        return captured

    resolve(fetch=fetch)
    with pytest.raises(QuotaDenied, match="grant_invalid"):
        resolve(fetch=fetch)


def test_real_http_adapter_contract_with_signed_response():
    def handler(request):
        data = json.loads(request.content)
        expected = hmac.new(
            SECRET,
            b"POST\n/internal/v1/assistant/core-plan-grant\n" + request.content,
            hashlib.sha256,
        ).hexdigest()
        assert request.headers["X-FM-Core-Plan-Signature"] == expected
        assert request.url.path == "/internal/v1/assistant/core-plan-grant"
        raw, signature = assertion(challenge=data["challenge"])
        return httpx.Response(
            200, content=raw,
            headers={"X-FM-Assistant-Plan-Signature": signature},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        port = AssistantPlanHTTPSFetch(
            origin="https://assistant.example.test", secret=SECRET,
            bounds=lambda capability: (100, 50), client=client,
        )
        policy = resolve(fetch=port)
        assert policy.revision == 3


def test_http_adapter_denies_provider_error_and_redirect():
    for status in (302, 401, 500):
        with httpx.Client(transport=httpx.MockTransport(
            lambda request, code=status: httpx.Response(
                code, headers={"location": "https://untrusted.example/"}
            )
        )) as client:
            port = AssistantPlanHTTPSFetch(
                origin="https://assistant.example.test", secret=SECRET,
                bounds=lambda capability: (100, 50), client=client,
            )
            with pytest.raises(QuotaDenied, match="grant_unavailable"):
                resolve(fetch=port)


def test_http_adapter_requires_https_and_trusted_bounds():
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: pytest.fail("provider contacted on invalid quota caps")
    )) as client:
        with pytest.raises(ValueError, match="endpoint_invalid"):
            AssistantPlanHTTPSFetch(
                origin="http://assistant.example.test", secret=SECRET,
                bounds=lambda capability: (100, 50), client=client,
            )
        port = AssistantPlanHTTPSFetch(
            origin="https://assistant.example.test", secret=SECRET,
            bounds=lambda capability: (True, 50), client=client,
        )
        with pytest.raises(QuotaDenied, match="bounds_invalid"):
            resolve(fetch=port)
