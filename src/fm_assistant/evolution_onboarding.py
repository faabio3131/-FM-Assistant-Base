"""FM-controlled WhatsApp QR onboarding over the existing Integration Fabric."""
from __future__ import annotations

from dataclasses import dataclass, field
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
            status="connecting" if qr_data_url else "connected",
            qr_data_url=qr_data_url,
        )
