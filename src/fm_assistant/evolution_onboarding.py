"""FM-controlled WhatsApp QR onboarding over the existing Integration Fabric."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .channels.whatsapp_evolution import EvolutionClient, EvolutionUnavailable
from .credential_vault import CredentialVault
from .domain import TenantContext
from .integration import (
    WHATSAPP_EVOLUTION_PROVIDER,
    CredentialSource,
    IntegrationConnection,
    IntegrationStatus,
)
from .integration_repository import IntegrationRepository
from .whatsapp_repository import WhatsAppInboundRepository


@dataclass(frozen=True, kw_only=True)
class QRConnection:
    connection_id: str
    status: str
    qr_data_url: str | None = field(repr=False)


class EvolutionOnboarding:
    PROVIDER = "whatsapp_evolution"

    def __init__(
        self, *, repository: IntegrationRepository,
        vault: CredentialVault, transport: EvolutionClient,
    ) -> None:
        self._repository = repository
        self._vault = vault
        self._transport = transport

    def provision(self, context: TenantContext) -> IntegrationConnection:
        current = self._repository.latest_for_provider(context, self.PROVIDER)
        if current is not None:
            # Failed/ambiguous external creates must not be replayed blindly.
            raise RuntimeError("evolution_existing_connection_requires_review")
        instance = "fm_" + uuid4().hex
        connection = self._repository.create_connection(
            context, provider=WHATSAPP_EVOLUTION_PROVIDER,
            config={"instance_name": instance}, status=IntegrationStatus.DRAFT,
        )
        try:
            token = self._transport.create(instance)
        except EvolutionUnavailable:
            self._repository.record_event(
                context, connection.connection_id,
                event_type="evolution.provision_ambiguous",
            )
            raise
        self._repository.store_secret(
            context, connection.connection_id,
            secret_name="instance_token",
            ciphertext=self._vault.encrypt(token),
            source=CredentialSource.FM_MANAGED,
        )
        self._repository.record_event(
            context, connection.connection_id,
            event_type="evolution.provisioned",
        )
        return connection

    def current(self, context: TenantContext) -> IntegrationConnection | None:
        """Read-only tenant/unit scoped QR integration for customer onboarding."""
        return self._repository.latest_for_provider(context, self.PROVIDER)

    def pause(self, context: TenantContext, connection_id: str) -> IntegrationConnection:
        """Block local inbound/outbound without claiming remote WhatsApp logout.

        Paused instances require a separate governed recovery procedure;
        an incoming 'open' event must NEVER reactivate them.
        """
        connection = self._repository.get(context, connection_id)
        if connection is None or connection.provider_key != self.PROVIDER:
            raise LookupError("evolution_connection_not_found")
        if connection.status is IntegrationStatus.REVOKED:
            raise RuntimeError("evolution_connection_revoked")
        if connection.status is IntegrationStatus.DISABLED:
            return connection
        updated = self._repository.update_connection(
            context, connection_id, status=IntegrationStatus.DISABLED,
            bump_revision=True,
        )
        self._repository.record_event(
            context, connection_id, event_type="evolution.paused_local",
        )
        return updated

    def logout(self, context: TenantContext, connection_id: str) -> IntegrationConnection:
        """Governed remote WhatsApp logout, guarded against ambiguous success.

        First disable locally to stop further inbound/worker processing.
        A failed remote operation NEVER becomes a claimed remote revocation.
        """
        connection = self._repository.get(context, connection_id)
        if connection is None or connection.provider_key != self.PROVIDER:
            raise LookupError("evolution_connection_not_found")
        if connection.status is IntegrationStatus.REVOKED:
            return connection
        # Leave local session disabled even if the remote request times out.
        if connection.status is not IntegrationStatus.DISABLED:
            connection = self.pause(context, connection_id)
        secrets = self._repository.active_secret_ciphertexts(connection_id)
        token_cipher = secrets.get("instance_token")
        if token_cipher is None:
            raise RuntimeError("evolution_logout_requires_review")
        self._repository.record_event(
            context, connection_id, event_type="evolution.logout_requested",
        )
        try:
            self._transport.logout(
                str(connection.config["instance_name"]),
                instance_token=self._vault.decrypt(token_cipher),
            )
        except EvolutionUnavailable:
            self._repository.record_event(
                context, connection_id, event_type="evolution.logout_ambiguous",
            )
            raise
        self._repository.revoke_secrets(context, connection_id)
        result = self._repository.update_connection(
            context, connection_id, status=IntegrationStatus.REVOKED,
            bump_revision=True,
        )
        self._repository.record_event(
            context, connection_id, event_type="evolution.logout_confirmed",
        )
        return result

    def quarantine_stale(
        self, context: TenantContext, *, connection_id: str,
        inbox: WhatsAppInboundRepository, older_than_seconds: int = 300,
    ) -> int:
        """Governed internal recovery hook, not exposed as a tenant API."""
        if type(older_than_seconds) is not int or not 60 <= older_than_seconds <= 86400:
            raise ValueError("evolution_recovery_window_invalid")
        connection = self._repository.get(context, connection_id)
        if connection is None or connection.provider_key != self.PROVIDER:
            raise LookupError("evolution_connection_not_found")
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        return inbox.quarantine_stale_processing(
            channel_id=connection_id, older_than=cutoff,
        )

    def qr(self, context: TenantContext, connection_id: str) -> QRConnection:
        connection = self._repository.get(context, connection_id)
        if connection is None or connection.provider_key != self.PROVIDER:
            raise LookupError("evolution_connection_not_found")
        if connection.status in {IntegrationStatus.REVOKED, IntegrationStatus.DISABLED}:
            raise RuntimeError("evolution_connection_not_enabled")
        metadata = self._repository.active_secret_ciphertexts(connection_id)
        if "instance_token" not in metadata:
            # Do not assume a previous ambiguous provision failed remotely.
            raise RuntimeError("evolution_provision_requires_review")
        qr_data_url = self._transport.connect(str(connection.config["instance_name"]))
        return QRConnection(
            connection_id=connection_id,
            status=(
                "connected" if not qr_data_url and connection.status is IntegrationStatus.ACTIVE
                else "connecting" if qr_data_url else "awaiting_confirmation"
            ),
            qr_data_url=qr_data_url,
        )
