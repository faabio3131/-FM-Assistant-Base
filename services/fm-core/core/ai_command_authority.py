"""Verificação fail-closed de identidade humana delegada pelo FM Command.

F3.6.2: biblioteca de autenticação/verificação apenas. Não habilita mutações.
O Core não emite identidade humana nem considera X-Core-Admin-Key como autorização.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import jwt


class CommandAuthorityDenied(PermissionError):
    """Falha uniforme sem revelar detalhes de assinatura ou identidade."""


@dataclass(frozen=True, kw_only=True)
class CommandTrustPolicy:
    issuer: str
    audience: str
    public_key_pem: str = field(repr=False)
    max_token_lifetime_seconds: int = 300
    max_step_up_age_seconds: int = 300
    clock_leeway_seconds: int = 15

    def __post_init__(self) -> None:
        if not self.issuer.strip() or not self.audience.strip():
            raise ValueError("command_trust_invalid")
        if not self.public_key_pem.startswith("-----BEGIN PUBLIC KEY-----"):
            raise ValueError("command_trust_key_invalid")
        if not 30 <= self.max_token_lifetime_seconds <= 300:
            raise ValueError("command_trust_lifetime_invalid")
        if not 30 <= self.max_step_up_age_seconds <= 300:
            raise ValueError("command_trust_step_up_invalid")
        if not 0 <= self.clock_leeway_seconds <= 30:
            raise ValueError("command_trust_leeway_invalid")


@dataclass(frozen=True, kw_only=True)
class VerifiedCommandAdmin:
    user_id: str
    session_id: str
    token_id: str
    issued_at: int
    expires_at: int
    step_up_at: int
    permissions: frozenset[str]


def verify_command_platform_admin(
    token: str,
    policy: CommandTrustPolicy,
    *,
    now: datetime | None = None,
) -> VerifiedCommandAdmin:
    """Verifica JWT RS256 assinado pelo Command, com step-up recente.

    Não é um verificador genérico de identidades: exige explicitamente
    ator humano, plataforma, papel e permissão administrativa. Cabe ao
    futuro serviço de mutação exigir adicionalmente idempotência,
    jti único, auditoria atômica e chave técnica segregada.
    """
    timestamp = int((now or datetime.now(UTC)).timestamp())
    if not token or len(token) > 8192:
        raise CommandAuthorityDenied("command_authority_denied")
    try:
        claims = jwt.decode(
            token,
            policy.public_key_pem,
            algorithms=["RS256"],
            issuer=policy.issuer,
            audience=policy.audience,
            leeway=policy.clock_leeway_seconds,
            options={
                "require": [
                    "iss", "aud", "sub", "jti", "iat", "nbf", "exp",
                    "session_id", "step_up_at",
                ],
            },
        )
        issued_at = claims["iat"]
        expires_at = claims["exp"]
        not_before = claims["nbf"]
        step_up_at = claims["step_up_at"]
        if any(type(value) is not int for value in (
            issued_at, expires_at, not_before, step_up_at
        )):
            raise ValueError("invalid_timestamp_type")
        if not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 128:
            raise ValueError("invalid_subject")
        if not isinstance(claims["session_id"], str) or not 1 <= len(claims["session_id"]) <= 128:
            raise ValueError("invalid_session")
        if not isinstance(claims["jti"], str) or not 16 <= len(claims["jti"]) <= 128:
            raise ValueError("invalid_jti")
        if claims.get("actor_type") != "human":
            raise ValueError("not_human")
        if claims.get("role") != "platform_admin":
            raise ValueError("not_platform_admin")
        if claims.get("scope") != "fm_core_platform":
            raise ValueError("invalid_scope")
        permissions = claims.get("permissions")
        if not isinstance(permissions, list) or not all(
            isinstance(permission, str) and len(permission) <= 128
            for permission in permissions
        ):
            raise ValueError("invalid_permissions")
        if "core.ai.admin.mutate" not in permissions:
            raise ValueError("missing_permission")
        if issued_at > timestamp + policy.clock_leeway_seconds:
            raise ValueError("issued_in_future")
        if expires_at <= issued_at or expires_at - issued_at > policy.max_token_lifetime_seconds:
            raise ValueError("lifetime_exceeded")
        if not_before < issued_at - policy.clock_leeway_seconds:
            raise ValueError("nbf_before_issue")
        if step_up_at > timestamp + policy.clock_leeway_seconds:
            raise ValueError("future_step_up")
        if step_up_at < issued_at - policy.max_step_up_age_seconds:
            raise ValueError("step_up_too_old_at_issue")
        if timestamp - step_up_at > policy.max_step_up_age_seconds:
            raise ValueError("step_up_expired")
        return VerifiedCommandAdmin(
            user_id=claims["sub"],
            session_id=claims["session_id"],
            token_id=claims["jti"],
            issued_at=issued_at,
            expires_at=expires_at,
            step_up_at=step_up_at,
            permissions=frozenset(permissions),
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise CommandAuthorityDenied("command_authority_denied") from exc
