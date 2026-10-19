"""Compatibilidade WhatsApp sobre o Integration Control Plane universal."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from .channels.whatsapp_meta import WhatsAppMetaConfig
from .db import IntegrationInboundORM
from .domain import TenantContext
from .integration import ResolvedIntegration
from .integration_service import IntegrationService


class WhatsAppChannelRepository:
    """Facade de compatibilidade; fonte de verdade é o Integration Fabric."""

    PROVIDER_KEY = "whatsapp_meta"

    def __init__(self, integrations: IntegrationService) -> None:
        self._integrations = integrations

    @staticmethod
    def _domain(resolved: ResolvedIntegration) -> WhatsAppMetaConfig:
        connection = resolved.connection
        config = connection.config
        return WhatsAppMetaConfig(
            channel_id=connection.connection_id,
            tenant_id=connection.tenant_id,
            unit_id=connection.unit_id,
            phone_number_id=str(config["phone_number_id"]),
            business_account_id=(
                str(config["business_account_id"])
                if config.get("business_account_id") is not None
                else None
            ),
            access_token=resolved.secrets["access_token"],
            app_secret=resolved.secrets["app_secret"],
            verify_token=resolved.secrets["verify_token"],
            graph_api_version=str(config.get("graph_api_version") or "v23.0"),
        )

    def configure(
        self,
        context: TenantContext,
        *,
        phone_number_id: str,
        business_account_id: str | None,
        access_token: str,
        app_secret: str,
        verify_token: str,
        graph_api_version: str,
    ) -> WhatsAppMetaConfig:
        connection = self._integrations.configure_compatibility_active(
            context,
            provider_key=self.PROVIDER_KEY,
            config={
                "phone_number_id": phone_number_id,
                "business_account_id": business_account_id,
                "graph_api_version": graph_api_version,
            },
            secrets={
                "access_token": access_token,
                "app_secret": app_secret,
                "verify_token": verify_token,
            },
        )
        resolved = self._integrations.resolve_active_for_provider(
            context,
            self.PROVIDER_KEY,
        )
        if resolved is None or resolved.connection.connection_id != connection.connection_id:
            raise RuntimeError("whatsapp_integration_resolution_failed")
        return self._domain(resolved)

    def get_for_context(self, context: TenantContext) -> WhatsAppMetaConfig | None:
        resolved = self._integrations.resolve_active_for_provider(
            context,
            self.PROVIDER_KEY,
        )
        return self._domain(resolved) if resolved is not None else None

    def get_by_channel_id(self, channel_id: str) -> WhatsAppMetaConfig | None:
        resolved = self._integrations.resolve_by_id_unscoped(
            channel_id,
            self.PROVIDER_KEY,
        )
        return self._domain(resolved) if resolved is not None else None


class WhatsAppInboundRepository:
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    RECONCILE_REQUIRED = "reconcile_required"

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def claim(
        self,
        *,
        channel_id: str,
        message_id: str,
        sender_hash: str,
        message_type: str,
    ) -> bool:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            row = IntegrationInboundORM(
                channel_id=channel_id,
                message_id=message_id,
                sender_hash=sender_hash,
                message_type=message_type,
                status=self.PROCESSING,
                outbound_id=None,
                error_code=None,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            try:
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                existing = session.get(IntegrationInboundORM, (channel_id, message_id))
                if existing is None or existing.status != self.FAILED:
                    return False
                existing.status = self.PROCESSING
                existing.error_code = None
                existing.updated_at = now
                session.commit()
                return True

    def _set_status(
        self,
        *,
        channel_id: str,
        message_id: str,
        status: str,
        outbound_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(IntegrationInboundORM, (channel_id, message_id))
            if row is None:
                raise LookupError("whatsapp_inbound_not_found")
            row.status = status
            row.outbound_id = outbound_id
            row.error_code = error_code
            row.updated_at = datetime.now(UTC)
            session.commit()

    def complete(self, *, channel_id: str, message_id: str, outbound_id: str | None) -> None:
        self._set_status(
            channel_id=channel_id,
            message_id=message_id,
            status=self.PROCESSED,
            outbound_id=outbound_id,
        )

    def mark_failed(self, *, channel_id: str, message_id: str, error_code: str) -> None:
        self._set_status(
            channel_id=channel_id,
            message_id=message_id,
            status=self.FAILED,
            error_code=error_code[:160],
        )

    def mark_reconcile(
        self,
        *,
        channel_id: str,
        message_id: str,
        error_code: str,
    ) -> None:
        self._set_status(
            channel_id=channel_id,
            message_id=message_id,
            status=self.RECONCILE_REQUIRED,
            error_code=error_code[:160],
        )

    def quarantine_stale_processing(
        self, *, channel_id: str, older_than: datetime, limit: int = 100,
    ) -> int:
        """Quarantine stranded delivery attempts; NEVER retry provider or Core.

        A bounded transactional sweep; conditional status/time update keeps
        concurrent state changes from being overwritten.
        """
        if older_than.tzinfo is None or not 1 <= limit <= 500:
            raise ValueError("inbound_recovery_invalid")
        cutoff = older_than.astimezone(UTC)
        now = datetime.now(UTC)
        with self._session_factory() as session:
            stmt = (
                select(IntegrationInboundORM.message_id)
                .where(
                    IntegrationInboundORM.channel_id == channel_id,
                    IntegrationInboundORM.status == self.PROCESSING,
                    IntegrationInboundORM.updated_at < cutoff,
                )
                .order_by(IntegrationInboundORM.updated_at, IntegrationInboundORM.message_id)
                .limit(limit)
            )
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            keys = session.scalars(stmt).all()
            changed = 0
            for message_id in keys:
                result = session.execute(
                    update(IntegrationInboundORM)
                    .where(
                        IntegrationInboundORM.channel_id == channel_id,
                        IntegrationInboundORM.message_id == message_id,
                        IntegrationInboundORM.status == self.PROCESSING,
                        IntegrationInboundORM.updated_at < cutoff,
                    )
                    .values(
                        status=self.RECONCILE_REQUIRED,
                        error_code="stale_processing_requires_reconciliation",
                        updated_at=now,
                    )
                )
                changed += result.rowcount
            session.commit()
            return changed

    def status(self, *, channel_id: str, message_id: str) -> str | None:
        with self._session_factory() as session:
            row = session.get(IntegrationInboundORM, (channel_id, message_id))
            return row.status if row is not None else None
