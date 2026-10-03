"""Persistência isolada do canal WhatsApp e ledger de idempotência."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .channel_secrets import ChannelSecretBox
from .channels.whatsapp_meta import WhatsAppMetaConfig
from .db import WhatsAppChannelORM, WhatsAppInboundORM
from .domain import TenantContext


class WhatsAppChannelRepository:
    def __init__(self, session_factory, secret_box: ChannelSecretBox) -> None:
        self._session_factory = session_factory
        self._secret_box = secret_box

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
        now = datetime.now(UTC)
        with self._session_factory() as session:
            row = session.scalar(
                select(WhatsAppChannelORM)
                .where(
                    WhatsAppChannelORM.tenant_id == context.tenant_id,
                    WhatsAppChannelORM.unit_id == context.unit_id,
                )
                .order_by(WhatsAppChannelORM.updated_at.desc())
                .limit(1)
            )
            channel_id = row.channel_id if row is not None else str(uuid4())
            config = WhatsAppMetaConfig(
                channel_id=channel_id,
                tenant_id=context.tenant_id,
                unit_id=context.unit_id,
                phone_number_id=phone_number_id.strip(),
                business_account_id=(business_account_id or "").strip() or None,
                access_token=access_token,
                app_secret=app_secret,
                verify_token=verify_token,
                graph_api_version=graph_api_version.strip(),
            )
            if row is None:
                row = WhatsAppChannelORM(
                    channel_id=channel_id,
                    tenant_id=context.tenant_id,
                    unit_id=context.unit_id,
                    phone_number_id=config.phone_number_id,
                    business_account_id=config.business_account_id,
                    access_token_ciphertext=self._secret_box.encrypt(config.access_token),
                    app_secret_ciphertext=self._secret_box.encrypt(config.app_secret),
                    verify_token_ciphertext=self._secret_box.encrypt(config.verify_token),
                    graph_api_version=config.graph_api_version,
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.phone_number_id = config.phone_number_id
                row.business_account_id = config.business_account_id
                row.access_token_ciphertext = self._secret_box.encrypt(config.access_token)
                row.app_secret_ciphertext = self._secret_box.encrypt(config.app_secret)
                row.verify_token_ciphertext = self._secret_box.encrypt(config.verify_token)
                row.graph_api_version = config.graph_api_version
                row.enabled = True
                row.updated_at = now
            session.commit()
            return config

    def _domain(self, row: WhatsAppChannelORM) -> WhatsAppMetaConfig:
        return WhatsAppMetaConfig(
            channel_id=row.channel_id,
            tenant_id=row.tenant_id,
            unit_id=row.unit_id,
            phone_number_id=row.phone_number_id,
            business_account_id=row.business_account_id,
            access_token=self._secret_box.decrypt(row.access_token_ciphertext),
            app_secret=self._secret_box.decrypt(row.app_secret_ciphertext),
            verify_token=self._secret_box.decrypt(row.verify_token_ciphertext),
            graph_api_version=row.graph_api_version,
        )

    def get_for_context(self, context: TenantContext) -> WhatsAppMetaConfig | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(WhatsAppChannelORM)
                .where(
                    WhatsAppChannelORM.tenant_id == context.tenant_id,
                    WhatsAppChannelORM.unit_id == context.unit_id,
                    WhatsAppChannelORM.enabled.is_(True),
                )
                .order_by(WhatsAppChannelORM.updated_at.desc())
                .limit(1)
            )
            return self._domain(row) if row is not None else None

    def get_by_channel_id(self, channel_id: str) -> WhatsAppMetaConfig | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(WhatsAppChannelORM).where(
                    WhatsAppChannelORM.channel_id == channel_id,
                    WhatsAppChannelORM.enabled.is_(True),
                )
            )
            return self._domain(row) if row is not None else None


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
            row = WhatsAppInboundORM(
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
                existing = session.get(WhatsAppInboundORM, (channel_id, message_id))
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
            row = session.get(WhatsAppInboundORM, (channel_id, message_id))
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

    def status(self, *, channel_id: str, message_id: str) -> str | None:
        with self._session_factory() as session:
            row = session.get(WhatsAppInboundORM, (channel_id, message_id))
            return row.status if row is not None else None
