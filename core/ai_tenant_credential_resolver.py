"""F3.7: porta BYOK por tenant para o Integration & Credential Control Plane.

Não há acesso implícito ao banco do Assistant, nem fallback para chaves da FM.
O gateway injetado deve aplicar, do lado autoritativo, status ACTIVE, secret
não revogado, entitlement e acesso tenant-scoped antes de devolver SecretValue.

Até existir um gateway autenticado e homologado, o bootstrap comercial segue
usando FMManagedCredentialResolver e BYOK permanece fail-closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from core.ai_control_plane import ControlPlaneError
from core.seguranca.segredos import SecretValue

_TENANT_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_OPAQUE_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,255}$")


@dataclass(frozen=True, kw_only=True)
class TenantSecretReference:
    tenant_id: str
    opaque_id: str = field(repr=False)

    def __repr__(self) -> str:
        return f"TenantSecretReference(tenant_id={self.tenant_id!r}, opaque_id=***)"


def parse_tenant_secret_reference(
    *, tenant_id: str, secret_reference: str
) -> TenantSecretReference:
    """Rejeita referência malformada/cross-tenant antes de acessar o vault.

    Contrato de referência F3: integration:<tenant_id>:<opaque_id>
    O ID é uma referência opaca, não uma chave de API ou ciphertext.
    """
    if not isinstance(tenant_id, str) or not _TENANT_PATTERN.fullmatch(tenant_id):
        raise ControlPlaneError("core_control_plane.byok_reference_invalid")
    if not isinstance(secret_reference, str) or len(secret_reference) > 512:
        raise ControlPlaneError("core_control_plane.byok_reference_invalid")
    parts = secret_reference.split(":")
    if len(parts) != 3 or parts[0] != "integration" or parts[1] != tenant_id:
        raise ControlPlaneError("core_control_plane.byok_tenant_mismatch")
    if not _OPAQUE_PATTERN.fullmatch(parts[2]):
        raise ControlPlaneError("core_control_plane.byok_reference_invalid")
    return TenantSecretReference(tenant_id=tenant_id, opaque_id=parts[2])


class TenantCredentialDenied(ControlPlaneError):
    """Negação BYOK não permite fallback para credenciais de outra origem."""


class FMProviderCredentialResolver(Protocol):
    def resolve(
        self, *, tenant_id: str, credential_source: str, secret_reference: str
    ) -> SecretValue: ...


class TenantCredentialGateway(Protocol):
    """Porta do serviço autoritativo de segredos, sem dependência do produto.

    A implementação concreta deve autenticar a identidade de serviço e comprovar
    tenant, licença/BYOK entitlement, capability, conexão ACTIVE, versão e rotação.
    Nunca deve permitir acesso sem escopo ou listar valores de segredo.
    """

    def resolve_active_secret(
        self, *, tenant_id: str, opaque_reference: str
    ) -> SecretValue: ...

    def resolve_scoped_secret(
        self, *, tenant_id: str, unit_id: str, capability: str, opaque_reference: str
    ) -> SecretValue: ...



class GovernedCredentialResolver:
    """Resolve credenciais FM e BYOK; não troca a origem em caso de falha."""

    def __init__(
        self,
        *,
        fm_credentials: FMProviderCredentialResolver,
        tenant_gateway: TenantCredentialGateway,
    ) -> None:
        self._fm = fm_credentials
        self._tenant = tenant_gateway

    def resolve(
        self, *, tenant_id: str, credential_source: str, secret_reference: str
    ) -> SecretValue:
        if credential_source == "fm_managed":
            if not secret_reference.startswith(("env:", "vault:")):
                raise ControlPlaneError("core_control_plane.fm_secret_reference_invalid")
            result = self._fm.resolve(
                tenant_id=tenant_id,
                credential_source=credential_source,
                secret_reference=secret_reference,
            )
        elif credential_source == "tenant_managed":
            try:
                parsed = parse_tenant_secret_reference(
                    tenant_id=tenant_id, secret_reference=secret_reference
                )
                result = self._tenant.resolve_active_secret(
                    tenant_id=parsed.tenant_id, opaque_reference=parsed.opaque_id
                )
            except Exception as exc:
                raise TenantCredentialDenied(
                    "core_control_plane.byok_credential_unavailable"
                ) from exc
        else:
            raise ControlPlaneError("core_control_plane.credential_source_invalid")
        if not isinstance(result, SecretValue):
            if credential_source == "tenant_managed":
                raise TenantCredentialDenied(
                    "core_control_plane.byok_credential_unavailable"
                )
            raise ControlPlaneError("core_control_plane.credential_result_invalid")
        return result

    def resolve_for_request(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        capability: str,
        credential_source: str,
        secret_reference: str,
    ) -> SecretValue:
        if credential_source != "tenant_managed":
            return self.resolve(
                tenant_id=tenant_id,
                credential_source=credential_source,
                secret_reference=secret_reference,
            )
        try:
            if not unit_id.strip() or not capability.strip():
                raise ValueError("scope_missing")
            parsed = parse_tenant_secret_reference(
                tenant_id=tenant_id, secret_reference=secret_reference
            )
            result = self._tenant.resolve_scoped_secret(
                tenant_id=parsed.tenant_id,
                unit_id=unit_id,
                capability=capability,
                opaque_reference=parsed.opaque_id,
            )
            if not isinstance(result, SecretValue):
                raise ValueError("invalid_result")
            return result
        except Exception as exc:
            raise TenantCredentialDenied(
                "core_control_plane.byok_credential_unavailable"
            ) from exc
