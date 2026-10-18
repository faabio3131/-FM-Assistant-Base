"""Pré-condições determinísticas para futura liberação interna de BYOK ao FM Core.

NÃO autentica o solicitante e NÃO entrega/decifra segredos. Um futuro adapter
service-to-service deverá primeiro validar identidade de serviço, tenant/unidade,
permissões e replay; só então consultar esta política e resolver a versão ativa
do segredo dentro de uma transação governada.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from .db import (
    EntitlementORM,
    IntegrationCapabilityORM,
    IntegrationConnectionORM,
    IntegrationProviderORM,
    IntegrationSecretVersionORM,
    TenantLicenseORM,
    TenantORM,
    UnitORM,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class CoreBYOKReleasePolicy:
    """Retorna somente decisão booleana; não revela motivo, IDs ou valores."""

    def __init__(self, session_factory) -> None:
        self._sessions = session_factory

    def eligible(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        connection_id: str,
        capability: str,
        now: datetime | None = None,
    ) -> bool:
        if not all(
            isinstance(value, str) and 0 < len(value.strip()) <= 160
            for value in (tenant_id, unit_id, connection_id, capability)
        ):
            return False
        current = _utc(now or datetime.now(UTC))
        with self._sessions() as db:
            tenant = db.get(TenantORM, tenant_id)
            unit = db.get(UnitORM, (tenant_id, unit_id))
            license_row = db.get(TenantLicenseORM, tenant_id)
            entitlement = db.get(EntitlementORM, (tenant_id, "ai.byok"))
            connection = db.scalar(
                select(IntegrationConnectionORM).where(
                    IntegrationConnectionORM.connection_id == connection_id,
                    IntegrationConnectionORM.tenant_id == tenant_id,
                    IntegrationConnectionORM.unit_id == unit_id,
                    IntegrationConnectionORM.status == "active",
                )
            )
            if (
                tenant is None or tenant.status != "active"
                or unit is None or unit.status != "active"
                or entitlement is None or not entitlement.enabled
                or license_row is None or license_row.status not in {"active", "trial"}
                or connection is None
            ):
                return False
            if (
                license_row.status == "trial"
                and (
                    license_row.trial_ends_at is None
                    or _utc(license_row.trial_ends_at) <= current
                )
            ):
                return False
            if (
                license_row.status == "active"
                and license_row.period_ends_at is not None
                and _utc(license_row.period_ends_at) <= current
            ):
                return False
            provider = db.get(IntegrationProviderORM, connection.provider_key)
            if (
                provider is None or not provider.enabled
                or provider.integration_type != "ai"
            ):
                return False
            permission = db.get(
                IntegrationCapabilityORM, (connection_id, capability)
            )
            if permission is None:
                return False
            # Não retorna ciphertext. Apenas confirma a existência de uma
            # versão BYOK ainda ativa, não expirada e não revogada.
            secret = db.scalar(
                select(IntegrationSecretVersionORM)
                .where(
                    IntegrationSecretVersionORM.connection_id == connection_id,
                    IntegrationSecretVersionORM.secret_name == "api_key",
                    IntegrationSecretVersionORM.source == "tenant_managed",
                    IntegrationSecretVersionORM.active.is_(True),
                    IntegrationSecretVersionORM.revoked_at.is_(None),
                )
                .order_by(IntegrationSecretVersionORM.version.desc())
                .limit(1)
            )
            if secret is None:
                return False
            if secret.expires_at is not None and _utc(secret.expires_at) <= current:
                return False
            return bool(
                (secret.storage_backend == "db_encrypted" and secret.ciphertext)
                or (
                    secret.storage_backend == "external_reference"
                    and secret.secret_reference
                )
            )
