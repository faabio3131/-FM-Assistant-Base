"""Identidade, sessão e RBAC comerciais do FM Assistant."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import StrEnum

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .domain import TenantContext


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    SALES_AGENT = "sales_agent"
    SUPPORT_AGENT = "support_agent"
    VIEWER = "viewer"


class Permission(StrEnum):
    TENANT_READ = "tenant.read"
    TENANT_MANAGE = "tenant.manage"
    UNIT_READ = "unit.read"
    UNIT_MANAGE = "unit.manage"
    USER_READ = "user.read"
    USER_INVITE = "user.invite"
    USER_MANAGE = "user.manage"
    ROLE_MANAGE = "role.manage"
    PERSONA_READ = "persona.read"
    PERSONA_MANAGE = "persona.manage"
    KNOWLEDGE_READ = "knowledge.read"
    KNOWLEDGE_MANAGE = "knowledge.manage"
    CONVERSATION_READ = "conversation.read"
    CONVERSATION_RESPOND = "conversation.respond"
    CONVERSATION_HANDOFF = "conversation.handoff"
    INTEGRATION_READ = "integration.read"
    INTEGRATION_MANAGE = "integration.manage"
    CRM_READ = "crm.read"
    CRM_MANAGE = "crm.manage"
    BILLING_READ = "billing.read"
    BILLING_MANAGE = "billing.manage"
    ANALYTICS_READ = "analytics.read"
    API_CREDENTIAL_MANAGE = "api_credential.manage"


_OWNER_PERMISSIONS = frozenset(
    {
        Permission.TENANT_READ,
        Permission.TENANT_MANAGE,
        Permission.UNIT_READ,
        Permission.UNIT_MANAGE,
        Permission.USER_READ,
        Permission.USER_INVITE,
        Permission.USER_MANAGE,
        Permission.ROLE_MANAGE,
        Permission.PERSONA_READ,
        Permission.PERSONA_MANAGE,
        Permission.KNOWLEDGE_READ,
        Permission.KNOWLEDGE_MANAGE,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_RESPOND,
        Permission.CONVERSATION_HANDOFF,
        Permission.INTEGRATION_READ,
        Permission.INTEGRATION_MANAGE,
        Permission.CRM_READ,
        Permission.CRM_MANAGE,
        Permission.BILLING_READ,
        Permission.BILLING_MANAGE,
        Permission.ANALYTICS_READ,
        Permission.API_CREDENTIAL_MANAGE,
    }
)

_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: _OWNER_PERMISSIONS,
    Role.ADMIN: frozenset(
        permission for permission in _OWNER_PERMISSIONS if permission is not Permission.BILLING_MANAGE
    ),
    Role.MANAGER: frozenset(
        {
            Permission.TENANT_READ,
            Permission.UNIT_READ,
            Permission.USER_READ,
            Permission.USER_INVITE,
            Permission.PERSONA_READ,
            Permission.PERSONA_MANAGE,
            Permission.KNOWLEDGE_READ,
            Permission.KNOWLEDGE_MANAGE,
            Permission.CONVERSATION_READ,
            Permission.CONVERSATION_RESPOND,
            Permission.CONVERSATION_HANDOFF,
            Permission.INTEGRATION_READ,
            Permission.CRM_READ,
            Permission.CRM_MANAGE,
            Permission.BILLING_READ,
            Permission.ANALYTICS_READ,
        }
    ),
    Role.SALES_AGENT: frozenset(
        {
            Permission.TENANT_READ,
            Permission.UNIT_READ,
            Permission.PERSONA_READ,
            Permission.KNOWLEDGE_READ,
            Permission.CONVERSATION_READ,
            Permission.CONVERSATION_RESPOND,
            Permission.CONVERSATION_HANDOFF,
            Permission.CRM_READ,
            Permission.CRM_MANAGE,
            Permission.ANALYTICS_READ,
        }
    ),
    Role.SUPPORT_AGENT: frozenset(
        {
            Permission.TENANT_READ,
            Permission.UNIT_READ,
            Permission.PERSONA_READ,
            Permission.KNOWLEDGE_READ,
            Permission.CONVERSATION_READ,
            Permission.CONVERSATION_RESPOND,
            Permission.CONVERSATION_HANDOFF,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.TENANT_READ,
            Permission.UNIT_READ,
            Permission.PERSONA_READ,
            Permission.KNOWLEDGE_READ,
            Permission.CONVERSATION_READ,
            Permission.CRM_READ,
            Permission.BILLING_READ,
            Permission.ANALYTICS_READ,
        }
    ),
}

MACHINE_PERMISSIONS = frozenset(
    {
        Permission.PERSONA_READ,
        Permission.PERSONA_MANAGE,
        Permission.KNOWLEDGE_READ,
        Permission.KNOWLEDGE_MANAGE,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_RESPOND,
        Permission.CONVERSATION_HANDOFF,
        Permission.INTEGRATION_READ,
        Permission.INTEGRATION_MANAGE,
    }
)


class PrincipalKind(StrEnum):
    USER = "user"
    API_CREDENTIAL = "api_credential"


@dataclass(frozen=True, kw_only=True)
class AuthContext:
    tenant: TenantContext
    actor_id: str
    kind: PrincipalKind
    permissions: frozenset[Permission]
    role: Role | None = None
    user_id: str | None = None
    session_id: str | None = None

    def require(self, permission: Permission) -> None:
        if permission not in self.permissions:
            raise PermissionError(f"permission_required:{permission.value}")


def permissions_for_role(role: Role) -> frozenset[Permission]:
    return _ROLE_PERMISSIONS[role]


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if len(normalized) > 320 or normalized.count("@") != 1:
        raise ValueError("email_invalid")
    local, domain = normalized.split("@", 1)
    if not local or not domain or "." not in domain:
        raise ValueError("email_invalid")
    return normalized


_PASSWORD_HASHER = PasswordHasher()


def validate_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < 12 or len(password) > 256:
        raise ValueError("password_policy_invalid")


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_session_token() -> str:
    return "fms_" + secrets.token_urlsafe(32)


def generate_invitation_token() -> str:
    return "fmi_" + secrets.token_urlsafe(32)


def generate_recovery_token() -> str:
    return "fmr_" + secrets.token_urlsafe(32)


def hash_opaque_token(token: str, pepper: str) -> str:
    if not token.strip() or not pepper.strip():
        raise ValueError("token_or_pepper_missing")
    return hmac.new(
        pepper.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def can_assign_role(actor_role: Role, target_role: Role) -> bool:
    if actor_role is Role.OWNER:
        return True
    if actor_role is Role.ADMIN:
        return target_role in {
            Role.MANAGER,
            Role.SALES_AGENT,
            Role.SUPPORT_AGENT,
            Role.VIEWER,
        }
    if actor_role is Role.MANAGER:
        return target_role in {
            Role.SALES_AGENT,
            Role.SUPPORT_AGENT,
            Role.VIEWER,
        }
    return False
