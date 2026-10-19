"""Contract security tests for signed Assistant policy assertions."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from core.ai_quota_store import QuotaDenied
from core.ai_signed_plan_authority import SignedAssistantPlanAuthority, signed_plan_body

NOW = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)
SECRET = b"assistant-to-core-test-secret-key-32-bytes-12345"


def assertion(**updates):
    obj = {
        "tenant_id": "tenant-a", "unit_id": "u1",
        "capability": "atendimento_interpretacao",
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
    payload = grant if grant is not None else assertion()
    authority = SignedAssistantPlanAuthority(
        secret=SECRET,
        fetch=fetch or (lambda t, u, c: payload),
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
    calls = [assertion()]
    def fetch(_tenant, _unit, _cap):
        if calls:
            return calls.pop()
        raise OSError("assistant unreachable")

    resolve(fetch=fetch)
    with pytest.raises(QuotaDenied, match="grant_unavailable"):
        resolve(fetch=fetch)
