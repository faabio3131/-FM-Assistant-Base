"""Autenticação SaaS: contexto de tenant derivado da credencial, nunca do cliente."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from .domain import TenantContext


def generate_api_key() -> str:
    return "fma_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str, pepper: str) -> str:
    key = api_key.strip()
    if not key:
        raise ValueError("api_key_obrigatoria")
    if not pepper.strip():
        raise ValueError("credential_pepper_obrigatorio")
    return hmac.new(
        pepper.encode("utf-8"),
        key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True, kw_only=True)
class Credential:
    credential_id: str
    tenant_id: str
    unit_id: str
    key_hash: str
    active: bool = True

    def context(self) -> TenantContext:
        if not self.active:
            raise PermissionError("credential_inactive")
        return TenantContext(
            tenant_id=self.tenant_id,
            unit_id=self.unit_id,
            credential_id=self.credential_id,
        )
