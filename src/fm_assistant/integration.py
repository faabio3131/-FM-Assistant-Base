"""Contratos universais do Integration & Credential Control Plane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class IntegrationStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    REVOKED = "revoked"


class CredentialSource(StrEnum):
    FM_MANAGED = "fm_managed"
    TENANT_MANAGED = "tenant_managed"


class VaultBackend(StrEnum):
    DB_ENCRYPTED = "db_encrypted"
    EXTERNAL_REFERENCE = "external_reference"


@dataclass(frozen=True, kw_only=True)
class IntegrationProviderDefinition:
    provider_key: str
    integration_type: str
    display_name: str
    definition_version: int
    config_fields: tuple[str, ...]
    required_config_fields: tuple[str, ...]
    secret_fields: tuple[str, ...]
    capabilities: tuple[str, ...]
    default_config: tuple[tuple[str, str], ...] = ()

    def defaults(self) -> dict[str, str]:
        return dict(self.default_config)


WHATSAPP_META_PROVIDER = IntegrationProviderDefinition(
    provider_key="whatsapp_meta",
    integration_type="whatsapp",
    display_name="WhatsApp Cloud API (Meta)",
    definition_version=1,
    config_fields=("phone_number_id", "business_account_id", "graph_api_version"),
    required_config_fields=("phone_number_id",),
    secret_fields=("access_token", "app_secret", "verify_token"),
    capabilities=("whatsapp.messaging", "whatsapp.webhook", "whatsapp.audio"),
    default_config=(("graph_api_version", "v23.0"),),
)

WHATSAPP_EVOLUTION_PROVIDER = IntegrationProviderDefinition(
    provider_key="whatsapp_evolution",
    integration_type="whatsapp",
    display_name="WhatsApp QR (FM managed)",
    definition_version=1,
    config_fields=("instance_name",),
    required_config_fields=("instance_name",),
    secret_fields=("instance_token",),
    capabilities=("whatsapp.messaging", "whatsapp.webhook", "whatsapp.qr"),
)

PROVIDER_CATALOG: dict[str, IntegrationProviderDefinition] = {
    WHATSAPP_META_PROVIDER.provider_key: WHATSAPP_META_PROVIDER,
    WHATSAPP_EVOLUTION_PROVIDER.provider_key: WHATSAPP_EVOLUTION_PROVIDER,
}


@dataclass(frozen=True, kw_only=True)
class IntegrationConnection:
    connection_id: str
    tenant_id: str
    unit_id: str
    provider_key: str
    integration_type: str
    status: IntegrationStatus
    config: dict[str, str | None]
    revision: int
    capabilities: tuple[str, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, kw_only=True)
class ResolvedIntegration:
    connection: IntegrationConnection
    secrets: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class ValidationResult:
    validation_id: str
    connection_id: str
    revision: int
    success: bool
    code: str
    created_at: datetime
