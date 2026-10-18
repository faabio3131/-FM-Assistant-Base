"""Casos de uso do Integration & Credential Control Plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .credential_vault import CredentialVault
from .domain import TenantContext
from .integration import (
    PROVIDER_CATALOG,
    CredentialSource,
    IntegrationConnection,
    IntegrationProviderDefinition,
    IntegrationStatus,
    ResolvedIntegration,
    ValidationResult,
)
from .integration_repository import IntegrationRepository


class IntegrationValidationError(RuntimeError):
    pass


@dataclass(frozen=True, kw_only=True)
class ProviderCatalogEntry:
    provider_key: str
    integration_type: str
    display_name: str
    definition_version: int
    config_fields: tuple[str, ...]
    required_config_fields: tuple[str, ...]
    secret_fields: tuple[str, ...]
    capabilities: tuple[str, ...]


class IntegrationService:
    def __init__(
        self,
        *,
        repository: IntegrationRepository,
        vault: CredentialVault,
    ) -> None:
        self._repository = repository
        self._vault = vault

    def ensure_catalog(self) -> None:
        for definition in PROVIDER_CATALOG.values():
            self._repository.ensure_provider(definition)

    @staticmethod
    def _definition(provider_key: str) -> IntegrationProviderDefinition:
        key = provider_key.strip().casefold()
        try:
            return PROVIDER_CATALOG[key]
        except KeyError as exc:
            raise LookupError("integration_provider_not_found") from exc

    def catalog(self) -> tuple[ProviderCatalogEntry, ...]:
        return tuple(
            ProviderCatalogEntry(
                provider_key=definition.provider_key,
                integration_type=definition.integration_type,
                display_name=definition.display_name,
                definition_version=definition.definition_version,
                config_fields=definition.config_fields,
                required_config_fields=definition.required_config_fields,
                secret_fields=definition.secret_fields,
                capabilities=definition.capabilities,
            )
            for definition in PROVIDER_CATALOG.values()
        )

    @staticmethod
    def _normalize_config(
        definition: IntegrationProviderDefinition,
        config: dict[str, Any],
    ) -> dict[str, str | None]:
        unknown = set(config) - set(definition.config_fields)
        if unknown:
            raise ValueError("integration_config_unknown_field")
        normalized: dict[str, str | None] = {
            key: value for key, value in definition.defaults().items()
        }
        for key, value in config.items():
            if value is None:
                normalized[key] = None
                continue
            if not isinstance(value, str):
                raise TypeError("integration_config_value_invalid")
            clean = value.strip()
            normalized[key] = clean or None
        for required in definition.required_config_fields:
            if not normalized.get(required):
                raise ValueError(f"integration_config_required:{required}")
        if definition.provider_key == "whatsapp_meta":
            version = normalized.get("graph_api_version") or ""
            if not version.startswith("v") or "." not in version:
                raise ValueError("whatsapp_meta_graph_version_invalid")
        return normalized

    @staticmethod
    def _normalize_secrets(
        definition: IntegrationProviderDefinition,
        secrets: dict[str, str],
        *,
        require_all: bool,
    ) -> dict[str, str]:
        unknown = set(secrets) - set(definition.secret_fields)
        if unknown:
            raise ValueError("integration_secret_unknown_field")
        result: dict[str, str] = {}
        for key, value in secrets.items():
            clean = value.strip()
            if not clean:
                raise ValueError(f"integration_secret_required:{key}")
            result[key] = clean
        if require_all:
            missing = set(definition.secret_fields) - set(result)
            if missing:
                raise ValueError("integration_secrets_incomplete")
        if not result:
            raise ValueError("integration_secret_required")
        return result

    def connect(
        self,
        context: TenantContext,
        *,
        provider_key: str,
        config: dict[str, Any],
        secrets: dict[str, str],
        source: CredentialSource = CredentialSource.TENANT_MANAGED,
    ) -> IntegrationConnection:
        definition = self._definition(provider_key)
        normalized_config = self._normalize_config(definition, config)
        normalized_secrets = self._normalize_secrets(
            definition,
            secrets,
            require_all=True,
        )
        connection = self._repository.create_connection(
            context,
            provider=definition,
            config=normalized_config,
            status=IntegrationStatus.DRAFT,
        )
        for secret_name, value in normalized_secrets.items():
            self._repository.store_secret(
                context,
                connection.connection_id,
                secret_name=secret_name,
                ciphertext=self._vault.encrypt(value),
                source=source,
            )
        self._repository.record_event(
            context,
            connection.connection_id,
            event_type="integration.connected",
            metadata={"provider": definition.provider_key},
        )
        return connection

    def update_config(
        self,
        context: TenantContext,
        connection_id: str,
        *,
        config: dict[str, Any],
    ) -> IntegrationConnection:
        connection = self._require_connection(context, connection_id)
        definition = self._definition(connection.provider_key)
        normalized = self._normalize_config(definition, config)
        updated = self._repository.update_connection(
            context,
            connection_id,
            config=normalized,
            status=IntegrationStatus.DRAFT,
            bump_revision=True,
        )
        self._repository.record_event(
            context,
            connection_id,
            event_type="integration.config_updated",
        )
        return updated

    def rotate(
        self,
        context: TenantContext,
        connection_id: str,
        *,
        secrets: dict[str, str],
        source: CredentialSource = CredentialSource.TENANT_MANAGED,
    ) -> IntegrationConnection:
        connection = self._require_connection(context, connection_id)
        if connection.status is IntegrationStatus.REVOKED:
            raise RuntimeError("integration_revoked")
        definition = self._definition(connection.provider_key)
        normalized = self._normalize_secrets(
            definition,
            secrets,
            require_all=False,
        )
        for secret_name, value in normalized.items():
            self._repository.store_secret(
                context,
                connection_id,
                secret_name=secret_name,
                ciphertext=self._vault.encrypt(value),
                source=source,
            )
        updated = self._repository.update_connection(
            context,
            connection_id,
            status=IntegrationStatus.DRAFT,
            bump_revision=True,
        )
        self._repository.record_event(
            context,
            connection_id,
            event_type="integration.credentials_rotated",
            metadata={"secret_count": len(normalized)},
        )
        return updated

    def validate(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> ValidationResult:
        connection = self._require_connection(context, connection_id)
        if connection.status is IntegrationStatus.REVOKED:
            raise RuntimeError("integration_revoked")
        validating = self._repository.update_connection(
            context,
            connection_id,
            status=IntegrationStatus.VALIDATING,
        )
        resolved = self._resolve(validating)
        try:
            metadata = self._remote_validate(resolved)
        except IntegrationValidationError as exc:
            result = self._repository.record_validation(
                context,
                connection_id,
                revision=validating.revision,
                success=False,
                code=str(exc),
            )
            self._repository.update_connection(
                context,
                connection_id,
                status=IntegrationStatus.DRAFT,
            )
            self._repository.record_event(
                context,
                connection_id,
                event_type="integration.validation_failed",
                metadata={"code": result.code},
            )
            return result

        result = self._repository.record_validation(
            context,
            connection_id,
            revision=validating.revision,
            success=True,
            code="ok",
            metadata=metadata,
        )
        self._repository.update_connection(
            context,
            connection_id,
            status=IntegrationStatus.DRAFT,
        )
        self._repository.record_event(
            context,
            connection_id,
            event_type="integration.validation_succeeded",
        )
        return result

    def activate(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> IntegrationConnection:
        connection = self._require_connection(context, connection_id)
        latest = self._repository.latest_validation(connection_id)
        if (
            latest is None
            or not latest.success
            or latest.revision != connection.revision
        ):
            raise RuntimeError("integration_validation_required")
        activated = self._repository.update_connection(
            context,
            connection_id,
            status=IntegrationStatus.ACTIVE,
        )
        self._repository.record_event(
            context,
            connection_id,
            event_type="integration.activated",
        )
        return activated

    def disable(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> IntegrationConnection:
        self._require_connection(context, connection_id)
        disabled = self._repository.update_connection(
            context,
            connection_id,
            status=IntegrationStatus.DISABLED,
        )
        self._repository.record_event(
            context,
            connection_id,
            event_type="integration.disabled",
        )
        return disabled

    def revoke(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> IntegrationConnection:
        self._require_connection(context, connection_id)
        self._repository.revoke_secrets(context, connection_id)
        revoked = self._repository.update_connection(
            context,
            connection_id,
            status=IntegrationStatus.REVOKED,
        )
        self._repository.record_event(
            context,
            connection_id,
            event_type="integration.revoked",
        )
        return revoked

    def list(self, context: TenantContext) -> tuple[IntegrationConnection, ...]:
        return self._repository.list_for_context(context)

    def get(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> IntegrationConnection:
        return self._require_connection(context, connection_id)

    def configure_compatibility_active(
        self,
        context: TenantContext,
        *,
        provider_key: str,
        config: dict[str, Any],
        secrets: dict[str, str],
    ) -> IntegrationConnection:
        definition = self._definition(provider_key)
        normalized_config = self._normalize_config(definition, config)
        normalized_secrets = self._normalize_secrets(
            definition,
            secrets,
            require_all=True,
        )
        existing = self._repository.latest_for_provider(context, definition.provider_key)
        if existing is None:
            connection = self._repository.create_connection(
                context,
                provider=definition,
                config=normalized_config,
                status=IntegrationStatus.ACTIVE,
            )
        else:
            if existing.status is IntegrationStatus.REVOKED:
                connection = self._repository.create_connection(
                    context,
                    provider=definition,
                    config=normalized_config,
                    status=IntegrationStatus.ACTIVE,
                )
            else:
                connection = self._repository.update_connection(
                    context,
                    existing.connection_id,
                    config=normalized_config,
                    status=IntegrationStatus.ACTIVE,
                    bump_revision=True,
                )
        for secret_name, value in normalized_secrets.items():
            self._repository.store_secret(
                context,
                connection.connection_id,
                secret_name=secret_name,
                ciphertext=self._vault.encrypt(value),
                source=CredentialSource.TENANT_MANAGED,
            )
        self._repository.record_event(
            context,
            connection.connection_id,
            event_type="integration.compatibility_configured",
            metadata={"provider": definition.provider_key},
        )
        return connection

    def resolve_active_for_provider(
        self,
        context: TenantContext,
        provider_key: str,
    ) -> ResolvedIntegration | None:
        connection = self._repository.latest_for_provider(
            context,
            provider_key,
            active_only=True,
        )
        return self._resolve(connection) if connection is not None else None

    def resolve_by_id_unscoped(
        self,
        connection_id: str,
        provider_key: str,
    ) -> ResolvedIntegration | None:
        connection = self._repository.get_unscoped(connection_id)
        if (
            connection is None
            or connection.provider_key != provider_key
            or connection.status is not IntegrationStatus.ACTIVE
        ):
            return None
        return self._resolve(connection)

    def _require_connection(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> IntegrationConnection:
        connection = self._repository.get(context, connection_id)
        if connection is None:
            raise LookupError("integration_not_found")
        return connection

    def _resolve(self, connection: IntegrationConnection) -> ResolvedIntegration:
        definition = self._definition(connection.provider_key)
        ciphertexts = self._repository.active_secret_ciphertexts(connection.connection_id)
        missing = set(definition.secret_fields) - set(ciphertexts)
        if missing:
            raise RuntimeError("integration_secrets_unavailable")
        secrets = {
            name: self._vault.decrypt(ciphertexts[name])
            for name in definition.secret_fields
        }
        return ResolvedIntegration(connection=connection, secrets=secrets)

    @staticmethod
    def _remote_validate(resolved: ResolvedIntegration) -> dict[str, str | int | bool]:
        if resolved.connection.provider_key == "whatsapp_meta":
            return IntegrationService._validate_whatsapp_meta(resolved)
        raise IntegrationValidationError("provider_validation_not_supported")

    @staticmethod
    def _validate_whatsapp_meta(
        resolved: ResolvedIntegration,
    ) -> dict[str, str | int | bool]:
        version = str(resolved.connection.config["graph_api_version"])
        phone_number_id = str(resolved.connection.config["phone_number_id"])
        token = resolved.secrets["access_token"]
        url = f"https://graph.facebook.com/{version}/{phone_number_id}"
        try:
            response = httpx.get(
                url,
                params={"fields": "id"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=8.0,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise IntegrationValidationError("provider_unavailable") from exc
        if response.status_code != 200:
            raise IntegrationValidationError("provider_rejected")
        try:
            payload = response.json()
        except ValueError as exc:
            raise IntegrationValidationError("provider_response_invalid") from exc
        if not isinstance(payload, dict) or str(payload.get("id", "")) != phone_number_id:
            raise IntegrationValidationError("provider_identity_mismatch")
        return {"provider_status": response.status_code, "identity_match": True}

