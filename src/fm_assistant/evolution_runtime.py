"""FM authenticated Evolution bridge to existing Assistant conversation runtime.

One inbound message ID is claimed in the existing channel inbox before model
or outbound execution. Ambiguous results require manual reconciliation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from .channels.evolution_events import EvolutionEventVerifier
from .channels.whatsapp_evolution import EvolutionClient, EvolutionUnavailable
from .credential_vault import CredentialVault
from .domain import Channel, ConversationStatus, TenantContext
from .integration import IntegrationStatus
from .integration_repository import IntegrationRepository
from .service import AssistantService
from .whatsapp_repository import WhatsAppInboundRepository


@dataclass(frozen=True, kw_only=True)
class EvolutionDeliveryResult:
    processed: int = 0
    duplicates: int = 0
    reconcile_required: int = 0


class EvolutionRuntime:
    def __init__(
        self, *, integrations: IntegrationRepository,
        inbox: WhatsAppInboundRepository, assistant: AssistantService,
        vault: CredentialVault, transport: EvolutionClient,
        verifier: EvolutionEventVerifier, sender_pepper: str,
    ) -> None:
        if not sender_pepper:
            raise ValueError("evolution_sender_pepper_required")
        self._integrations = integrations
        self._inbox = inbox
        self._assistant = assistant
        self._vault = vault
        self._transport = transport
        self._verifier = verifier
        self._pepper = sender_pepper.encode()

    def receive(
        self, *, connection_id: str, raw: bytes,
        signature: str | None, timestamp: str | None,
        at: datetime | None = None,
    ) -> EvolutionDeliveryResult:
        connection = self._integrations.get_unscoped(connection_id)
        if connection is None or connection.provider_key != "whatsapp_evolution":
            raise LookupError("evolution_connection_not_found")
        if connection.status in {IntegrationStatus.DISABLED, IntegrationStatus.REVOKED}:
            raise PermissionError("evolution_connection_inactive")
        instance = connection.config.get("instance_name")
        if not isinstance(instance, str):
            raise PermissionError("evolution_connection_invalid")
        messages = self._verifier.parse(
            connection_id=connection_id, expected_instance=instance,
            raw=raw, signature=signature, timestamp=timestamp,
            now=at or datetime.now(UTC),
        )
        payload = json.loads(raw)
        context = TenantContext(
            tenant_id=connection.tenant_id, unit_id=connection.unit_id,
            credential_id="channel:" + connection_id,
        )
        if payload.get("event") == "connection.update":
            state = payload.get("data")
            state = state.get("state") if isinstance(state, dict) else None
            if state == "open" and connection.status is not IntegrationStatus.ACTIVE:
                if "instance_token" not in self._integrations.active_secret_ciphertexts(
                    connection_id
                ):
                    raise PermissionError("evolution_connection_unprovisioned")
                self._integrations.update_connection(
                    context, connection_id, status=IntegrationStatus.ACTIVE,
                )
                self._integrations.record_event(
                    context, connection_id, event_type="evolution.connected",
                )
            elif state == "close" and connection.status is IntegrationStatus.ACTIVE:
                self._integrations.update_connection(
                    context, connection_id, status=IntegrationStatus.DEGRADED,
                )
                self._integrations.record_event(
                    context, connection_id, event_type="evolution.disconnected",
                )
            return EvolutionDeliveryResult()
        if connection.status is not IntegrationStatus.ACTIVE:
            raise PermissionError("evolution_connection_inactive")
        secret = self._integrations.active_secret_ciphertexts(connection_id).get(
            "instance_token"
        )
        if secret is None:
            raise PermissionError("evolution_connection_unprovisioned")
        processed = duplicates = reconcile = 0
        for item in messages:
            sender_hash = hmac.new(
                self._pepper, f"{connection_id}:{item.sender}".encode(),
                hashlib.sha256,
            ).hexdigest()
            if not self._inbox.claim(
                channel_id=connection_id, message_id=item.message_id,
                sender_hash=sender_hash, message_type="text",
            ):
                duplicates += 1
                continue
            try:
                conversation = self._assistant.get_or_create_external_conversation(
                    context=context, channel=Channel.WHATSAPP,
                    external_ref=f"wae:{connection_id}:{sender_hash}",
                )
                if conversation.status is ConversationStatus.HUMAN_HANDOFF:
                    self._inbox.complete(
                        channel_id=connection_id, message_id=item.message_id,
                        outbound_id=None,
                    )
                else:
                    reply = self._assistant.send_message(
                        context=context,
                        conversation_id=conversation.conversation_id,
                        content=item.text,
                    )
                    outbound_id = self._transport.send_text(
                        instance, instance_token=self._vault.decrypt(secret),
                        recipient=item.sender, message=reply.content,
                    )
                    self._inbox.complete(
                        channel_id=connection_id, message_id=item.message_id,
                        outbound_id=outbound_id,
                    )
                processed += 1
            except Exception:
                # A message may already have been committed or sent. Do not
                # retry from a duplicate webhook without operator review.
                self._inbox.mark_reconcile(
                    channel_id=connection_id, message_id=item.message_id,
                    error_code="evolution_outcome_uncertain",
                )
                reconcile += 1
        return EvolutionDeliveryResult(
            processed=processed, duplicates=duplicates,
            reconcile_required=reconcile,
        )
