from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from core.ai_command_authority import (
    CommandAuthorityDenied,
    CommandTrustPolicy,
    verify_command_platform_admin,
)


@pytest.fixture
def authority():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    policy = CommandTrustPolicy(
        issuer="fm-command-test",
        audience="fm-core-admin-test",
        public_key_pem=public_pem,
    )
    return key, policy


def _claims(**overrides):
    now = int(datetime.now(UTC).timestamp())
    base = {
        "iss": "fm-command-test",
        "aud": "fm-core-admin-test",
        "sub": "user-platform-1",
        "jti": "unique-token-jti-123456789",
        "iat": now,
        "nbf": now,
        "exp": now + 90,
        "session_id": "command-session-1",
        "step_up_at": now,
        "actor_type": "human",
        "role": "platform_admin",
        "scope": "fm_core_platform",
        "permissions": ["core.ai.admin.mutate"],
    }
    base.update(overrides)
    return base


def _token(key, claims, *, algorithm="RS256"):
    return jwt.encode(claims, key, algorithm=algorithm)


def test_accepts_only_verified_human_platform_admin_with_recent_step_up(authority):
    key, policy = authority
    principal = verify_command_platform_admin(_token(key, _claims()), policy)
    assert principal.user_id == "user-platform-1"
    assert principal.session_id == "command-session-1"
    assert principal.token_id == "unique-token-jti-123456789"
    assert principal.permissions == frozenset({"core.ai.admin.mutate"})
    assert "PUBLIC KEY" not in repr(policy)


@pytest.mark.parametrize(
    "overrides",
    [
        {"actor_type": "service"},
        {"role": "tenant_owner"},
        {"scope": "tenant-a"},
        {"permissions": ["core.ai.read"]},
        {"permissions": "core.ai.admin.mutate"},
        {"jti": "short"},
        {"session_id": ""},
        {"sub": ""},
        {"step_up_at": 0},
        {"iat": 0},
    ],
)
def test_rejects_wrong_authority_scope_or_stale_step_up(authority, overrides):
    key, policy = authority
    with pytest.raises(CommandAuthorityDenied, match="command_authority_denied"):
        verify_command_platform_admin(_token(key, _claims(**overrides)), policy)


def test_rejects_wrong_issuer_audience_signature_or_algorithm(authority):
    key, policy = authority
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for token in (
        _token(key, _claims(iss="untrusted")),
        _token(key, _claims(aud="another-service")),
        _token(other_key, _claims()),
        jwt.encode(_claims(), "untrusted-secret", algorithm="HS256"),
    ):
        with pytest.raises(CommandAuthorityDenied, match="command_authority_denied"):
            verify_command_platform_admin(token, policy)


def test_rejects_long_lifetime_or_expired_token(authority):
    key, policy = authority
    now = int(datetime.now(UTC).timestamp())
    for claims in (
        _claims(exp=now + 3600),
        _claims(exp=now - 60),
    ):
        with pytest.raises(CommandAuthorityDenied):
            verify_command_platform_admin(_token(key, claims), policy)


def test_rejects_missing_mandatory_claims_and_unconfigured_trust(authority):
    key, policy = authority
    data = _claims()
    del data["session_id"]
    with pytest.raises(CommandAuthorityDenied):
        verify_command_platform_admin(_token(key, data), policy)
    with pytest.raises(ValueError, match="command_trust_key_invalid"):
        replace(policy, public_key_pem="not-a-public-key")


def test_service_key_cannot_be_used_as_command_identity(authority):
    _, policy = authority
    for value in ("", "X-Core-Service-Key", "X-Core-Admin-Key", "abc.def.ghi"):
        with pytest.raises(CommandAuthorityDenied):
            verify_command_platform_admin(value, policy)
