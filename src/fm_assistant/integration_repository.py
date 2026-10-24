"""PersistÃªncia tenant-scoped do Integration Control Plane."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from .db import (
    EvolutionWebhookReceiptORM,
    IntegrationCapabilityORM,
    IntegrationConnectionORM,
    IntegrationEventORM,
    IntegrationProviderORM,
    IntegrationSecretVersionORM,
    IntegrationValidationORM,
)
from .domain import TenantContext
from .integration import (
    CredentialSource,
    IntegrationConnection,
    IntegrationProviderDefinition,
    IntegrationStatus,
    ValidationResult,
    VaultBackend,
)


@dataclass(frozen=True, kw_only=True)
class SecretVersionMetadata:
    secret_name: str
    version: int
    source: CredentialSource
    storage_backend: VaultBackend
    active: bool
    expires_at: datetime | None
    revoked_at: datetime | None


class IntegrationRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def ensure_provider(self, definition: IntegrationProviderDefinition) -> None:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(IntegrationProviderORM, definition.provider_key)
            if row is None:
                session.add(
                    IntegrationProviderORM(
                        provider_key=definition.provider_key,
                        integration_type=definition.integration_type,
                        display_name=definition.display_name,
                        definition_version=definition.definition_version,
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                row.integration_type = definition.integration_type
                row.display_name = definition.display_name
                row.definition_version = definition.definition_version
                row.enabled = True
                row.updated_at = now
            session.commit()

    @staticmethod
    def _domain(
        row: IntegrationConnectionORM,
        capabilities: tuple[str, ...],
    ) -> IntegrationConnection:
        raw_config = json.loads(row.config_json)
        if not isinstance(raw_config, dict):
            raise TypeError("integration_config_corrupt")
        config: dict[str, str | None] = {}
        for key, value in raw_config.items():
            if value is not None and not isinstance(value, str):
                raise TypeError("integration_config_corrupt")
            config[str(key)] = value
        return IntegrationConnection(
            connection_id=row.connection_id,
            tenant_id=row.tenant_id,
            unit_id=row.unit_id,
            provider_key=row.provider_key,
            integration_type=row.integration_type,
            status=IntegrationStatus(row.status),
            config=config,
            revision=row.revision,
            capabilities=capabilities,
            created_at=row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
            updated_at=row.updated_at.replace(tzinfo=row.updated_at.tzinfo or UTC),
        )

    def _capabilities(self, session, connection_id: str) -> tuple[str, ...]:
        return tuple(
            session.scalars(
                select(IntegrationCapabilityORM.capability)
                .where(IntegrationCapabilityORM.connection_id == connection_id)
                .order_by(IntegrationCapabilityORM.capability)
            ).all()
        )

    def create_connection(
        self,
        context: TenantContext,
        *,
        provider: IntegrationProviderDefinition,
        config: dict[str, str | None],
        status: IntegrationStatus,
        connection_id: str | None = None,
    ) -> IntegrationConnection:
        now = datetime.now(UTC)
        identifier = connection_id or str(uuid4())
        with self._session_factory() as session:
            if provider.provider_key == "whatsapp_evolution":
                # Serialize first provision even when two workers race before
                # the initial connection exists. Do not affect other providers.
                if session.bind is not None and session.bind.dialect.name == "postgresql":
                    session.execute(
                        text("SELECT pg_advisory_xact_lock(hashtext(:tenant), hashtext(:unit))"),
                        {"tenant": context.tenant_id, "unit": context.unit_id},
                    )
                existing = session.scalar(select(IntegrationConnectionORM.connection_id).where(
                    IntegrationConnectionORM.tenant_id == context.tenant_id,
                    IntegrationConnectionORM.unit_id == context.unit_id,
                    IntegrationConnectionORM.provider_key == "whatsapp_evolution",
                    IntegrationConnectionORM.status != IntegrationStatus.REVOKED.value,
                ).limit(1))
                if existing is not None:
                    raise RuntimeError("evolution_existing_connection_requires_review")
            row = IntegrationConnectionORM(
                connection_id=identifier,
                tenant_id=context.tenant_id,
                unit_id=context.unit_id,
                provider_key=provider.provider_key,
                integration_type=provider.integration_type,
                status=status.value,
                config_json=json.dumps(config, sort_keys=True, separators=(",", ":")),
                revision=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            for capability in provider.capabilities:
                session.add(
                    IntegrationCapabilityORM(
                        connection_id=identifier,
                        capability=capability,
                    )
                )
            session.commit()
            return self._domain(row, tuple(sorted(provider.capabilities)))

    def update_connection(
        self,
        context: TenantContext,
        connection_id: str,
        *,
        config: dict[str, str | None] | None = None,
        status: IntegrationStatus | None = None,
        bump_revision: bool = False,
    ) -> IntegrationConnection:
        with self._session_factory() as session:
            row = session.scalar(
                select(IntegrationConnectionORM).where(
                    IntegrationConnectionORM.connection_id == connection_id,
                    IntegrationConnectionORM.tenant_id == context.tenant_id,
                    IntegrationConnectionORM.unit_id == context.unit_id,
                ).with_for_update()
            )
            if row is None:
                raise LookupError("integration_not_found")
            if row.status == IntegrationStatus.REVOKED.value and status is not IntegrationStatus.REVOKED:
                raise RuntimeError("integration_revoked")
            if config is not None:
                row.config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
            if status is not None:
                row.status = status.value
            if bump_revision:
                row.revision += 1
            row.updated_at = datetime.now(UTC)
            session.commit()
            return self._domain(row, self._capabilities(session, row.connection_id))

    def get(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> IntegrationConnection | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(IntegrationConnectionORM).where(
                    IntegrationConnectionORM.connection_id == connection_id,
                    IntegrationConnectionORM.tenant_id == context.tenant_id,
                    IntegrationConnectionORM.unit_id == context.unit_id,
                )
            )
            if row is None:
                return None
            return self._domain(row, self._capabilities(session, row.connection_id))

    def get_unscoped(self, connection_id: str) -> IntegrationConnection | None:
        with self._session_factory() as session:
            row = session.get(IntegrationConnectionORM, connection_id)
            if row is None:
                return None
            return self._domain(row, self._capabilities(session, row.connection_id))

    def latest_for_provider(
        self,
        context: TenantContext,
        provider_key: str,
        *,
        active_only: bool = False,
    ) -> IntegrationConnection | None:
        with self._session_factory() as session:
            statement = select(IntegrationConnectionORM).where(
                IntegrationConnectionORM.tenant_id == context.tenant_id,
                IntegrationConnectionORM.unit_id == context.unit_id,
                IntegrationConnectionORM.provider_key == provider_key,
            )
            if active_only:
                statement = statement.where(
                    IntegrationConnectionORM.status == IntegrationStatus.ACTIVE.value
                )
            row = session.scalar(
                statement.order_by(IntegrationConnectionORM.updated_at.desc()).limit(1)
            )
            if row is None:
                return None
            return self._domain(row, self._capabilities(session, row.connection_id))

    def list_for_context(self, context: TenantContext) -> tuple[IntegrationConnection, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(IntegrationConnectionORM)
                .where(
                    IntegrationConnectionORM.tenant_id == context.tenant_id,
                    IntegrationConnectionORM.unit_id == context.unit_id,
                )
                .order_by(
                    IntegrationConnectionORM.integration_type,
                    IntegrationConnectionORM.created_at,
                )
            ).all()
            return tuple(
                self._domain(row, self._capabilities(session, row.connection_id))
                for row in rows
            )

    def store_secret(
        self,
        context: TenantContext,
        connection_id: str,
        *,
        secret_name: str,
        ciphertext: str,
        source: CredentialSource,
        expires_at: datetime | None = None,
    ) -> SecretVersionMetadata:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            connection = session.scalar(
                select(IntegrationConnectionORM).where(
                    IntegrationConnectionORM.connection_id == connection_id,
                    IntegrationConnectionORM.tenant_id == context.tenant_id,
                    IntegrationConnectionORM.unit_id == context.unit_id,
                )
            )
            if connection is None:
                raise LookupError("integration_not_found")
            previous = session.scalars(
                select(IntegrationSecretVersionORM).where(
                    IntegrationSecretVersionORM.connection_id == connection_id,
                    IntegrationSecretVersionORM.secret_name == secret_name,
                    IntegrationSecretVersionORM.active.is_(True),
                )
            ).all()
            for row in previous:
                row.active = False
            max_version = session.scalar(
                select(func.max(IntegrationSecretVersionORM.version)).where(
                    IntegrationSecretVersionORM.connection_id == connection_id,
                    IntegrationSecretVersionORM.secret_name == secret_name,
                )
            )
            version = int(max_version or 0) + 1
            row = IntegrationSecretVersionORM(
                connection_id=connection_id,
                secret_name=secret_name,
                version=version,
                source=source.value,
                storage_backend=VaultBackend.DB_ENCRYPTED.value,
                ciphertext=ciphertext,
                secret_reference=None,
                active=True,
                expires_at=expires_at,
                revoked_at=None,
                created_at=now,
            )
            session.add(row)
            session.commit()
            return SecretVersionMetadata(
                secret_name=secret_name,
                version=version,
                source=source,
                storage_backend=VaultBackend.DB_ENCRYPTED,
                active=True,
                expires_at=expires_at,
                revoked_at=None,
            )

    def claim_evolution_webhook(
        self, *, connection_id: str, digest: str,
    ) -> bool:
        """One-shot receipt for verified connection events across workers.

        A receipt is committed before transition; failures never replay
        an uncertain transition automatically.
        """
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("evolution_receipt_digest_invalid")
        with self._session_factory() as session:
            session.add(EvolutionWebhookReceiptORM(
                connection_id=connection_id, event_digest=digest,
                received_at=datetime.now(UTC),
            ))
            try:
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                return False

    def active_secret_ciphertexts(self, connection_id: str) -> dict[str, str]:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            rows = session.scalars(
                select(IntegrationSecretVersionORM).where(
                    IntegrationSecretVersionORM.connection_id == connection_id,
                    IntegrationSecretVersionORM.active.is_(True),
                    IntegrationSecretVersionORM.revoked_at.is_(None),
                )
            ).all()
            result: dict[str, str] = {}
            for row in rows:
                expires_at = row.expires_at
                if expires_at is not None:
                    expires_at = expires_at.replace(tzinfo=expires_at.tzinfo or UTC)
                    if expires_at <= now:
                        continue
                if row.storage_backend != VaultBackend.DB_ENCRYPTED.value or not row.ciphertext:
                    raise RuntimeError("integration_secret_backend_unavailable")
                result[row.secret_name] = row.ciphertext
            return result

    def secret_metadata(
        self,
        context: TenantContext,
        connection_id: str,
    ) -> tuple[SecretVersionMetadata, ...]:
        if self.get(context, connection_id) is None:
            raise LookupError("integration_not_found")
        with self._session_factory() as session:
            rows = session.scalars(
                select(IntegrationSecretVersionORM)
                .where(IntegrationSecretVersionORM.connection_id == connection_id)
                .order_by(
                    IntegrationSecretVersionORM.secret_name,
                    IntegrationSecretVersionORM.version,
                )
            ).all()
            return tuple(
                SecretVersionMetadata(
                    secret_name=row.secret_name,
                    version=row.version,
                    source=CredentialSource(row.source),
                    storage_backend=VaultBackend(row.storage_backend),
                    active=row.active,
                    expires_at=(
                        row.expires_at.replace(tzinfo=row.expires_at.tzinfo or UTC)
                        if row.expires_at is not None
                        else None
                    ),
                    revoked_at=(
                        row.revoked_at.replace(tzinfo=row.revoked_at.tzinfo or UTC)
                        if row.revoked_at is not None
                        else None
                    ),
                )
                for row in rows
            )

    def revoke_secrets(self, context: TenantContext, connection_id: str) -> None:
        if self.get(context, connection_id) is None:
            raise LookupError("integration_not_found")
        now = datetime.now(UTC)
        with self._session_factory() as session:
            rows = session.scalars(
                select(IntegrationSecretVersionORM).where(
                    IntegrationSecretVersionORM.connection_id == connection_id,
                    IntegrationSecretVersionORM.revoked_at.is_(None),
                )
            ).all()
            for row in rows:
                row.active = False
                row.revoked_at = now
            session.commit()

    def record_validation(
        self,
        context: TenantContext,
        connection_id: str,
        *,
        revision: int,
        success: bool,
        code: str,
        metadata: dict[str, str | int | bool] | None = None,
    ) -> ValidationResult:
        if self.get(context, connection_id) is None:
            raise LookupError("integration_not_found")
        now = datetime.now(UTC)
        validation_id = str(uuid4())
        with self._session_factory() as session:
            session.add(
                IntegrationValidationORM(
                    validation_id=validation_id,
                    connection_id=connection_id,
                    revision=revision,
                    success=success,
                    code=code[:160],
                    metadata_json=json.dumps(
                        metadata or {},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    created_at=now,
                )
            )
            session.commit()
        return ValidationResult(
            validation_id=validation_id,
            connection_id=connection_id,
            revision=revision,
            success=success,
            code=code[:160],
            created_at=now,
        )

    def latest_validation(self, connection_id: str) -> ValidationResult | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(IntegrationValidationORM)
                .where(IntegrationValidationORM.connection_id == connection_id)
                .order_by(IntegrationValidationORM.created_at.desc())
                .limit(1)
            )
            if row is None:
                return None
            return ValidationResult(
                validation_id=row.validation_id,
                connection_id=row.connection_id,
                revision=row.revision,
                success=row.success,
                code=row.code,
                created_at=row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
            )

    def record_event(
        self,
        context: TenantContext,
        connection_id: str,
        *,
        event_type: str,
        metadata: dict[str, str | int | bool] | None = None,
    ) -> None:
        if self.get(context, connection_id) is None:
            raise LookupError("integration_not_found")
        with self._session_factory() as session:
            session.add(
                IntegrationEventORM(
                    event_id=str(uuid4()),
                    connection_id=connection_id,
                    tenant_id=context.tenant_id,
                    unit_id=context.unit_id,
                    actor_id=context.credential_id,
                    event_type=event_type[:120],
                    metadata_json=json.dumps(
                        metadata or {},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
