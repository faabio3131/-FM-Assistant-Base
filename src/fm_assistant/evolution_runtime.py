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
from .channels.whatsapp_evolution import EvolutionClient
from .credential_vault import CredentialVault
from .domain import Channel, ConversationStatus, TenantContext
from .evolution_queue import EvolutionInboundQueue, QueuedInbound
from .integration import IntegrationStatus
from .integration_repository import IntegrationRepository
from .service import AssistantService
from .whatsapp_repository import WhatsAppInboundRepository


@dataclass(frozen=True, kw_only=True)
class EvolutionDeliveryResult:
    processed: int = 0
    duplicates: int = 0
    reconcile_required: int = 0
    queued: int = 0


class EvolutionRuntime:
    def __init__(
        self, *, integrations: IntegrationRepository,
        inbox: WhatsAppInboundRepository, assistant: AssistantService,
        vault: CredentialVault, transport: EvolutionClient,
        verifier: EvolutionEventVerifier, sender_pepper: str,
        queue: EvolutionInboundQueue | None = None,
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
        self._queue = queue

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
            # Deduplicate the authenticated delivery before state changes.
            # Include the signed time to distinguish independent lifecycle
            # notifications sharing the same body.
            receipt_digest = hashlib.sha256(
                (timestamp or "").encode("ascii") + b"\\n" + raw
            ).hexdigest()
            if not self._integrations.claim_evolution_webhook(
                connection_id=connection_id, digest=receipt_digest,
            ):
                return EvolutionDeliveryResult()
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
        if self._queue is not None:
            queued = duplicates = 0
            for item in messages:
                if self._queue.enqueue(
                    connection_id=connection_id, message_id=item.message_id,
                    sender=item.sender, text=item.text,
                ):
                    queued += 1
                else:
                    duplicates += 1
            return EvolutionDeliveryResult(
                processed=0, duplicates=duplicates,
                reconcile_required=0, queued=queued,
            )
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
            except Exception:  # noqa: BLE001 - quarantine any ambiguous side effect
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

    def recover_stale(self, *, older_than_seconds: int = 300) -> int:
        """Quarantine expired worker claims; never replay uncertain side effects."""
        if self._queue is None:
            raise RuntimeError("evolution_queue_not_configured")
        return self._queue.quarantine_stale(
            older_than_seconds=older_than_seconds,
        )

    def process_pending(self, *, limit: int = 10) -> EvolutionDeliveryResult:
        """Internal worker batch. No HTTP route or automatic background side effects."""
        if self._queue is None:
            raise RuntimeError("evolution_queue_not_configured")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("evolution_worker_limit_invalid")
        processed = duplicates = reconcile = 0
        for _ in range(limit):
            item = self._queue.claim()
            if item is None:
                break
            try:
                completed = self._process_queued(item)
                if completed:
                    processed += 1
                else:
                    duplicates += 1
                self._queue.finish(
                    connection_id=item.connection_id, message_id=item.message_id,
                    reconciled=False,
                    claim_generation=item.claim_generation,
                )
            except Exception:  # noqa: BLE001 - quarantine uncertain AI/provider side effects
                # A concurrent sweeper may already have quarantined this job.
                # Never reopen it or replay a provider send.
                if self._queue.state(
                    connection_id=item.connection_id, message_id=item.message_id,
                ) == "processing":
                    try:
                        self._queue.finish(
                            connection_id=item.connection_id, message_id=item.message_id,
                            reconciled=True, code="evolution_worker_uncertain",
                            claim_generation=item.claim_generation,
                        )
                    except RuntimeError:
                        # A competing sweeper or generation change won the race.
                        pass
                reconcile += 1
        return EvolutionDeliveryResult(
            processed=processed, duplicates=duplicates, reconcile_required=reconcile,
        )

    def _process_queued(self, item: QueuedInbound) -> bool:
        connection = self._integrations.get_unscoped(item.connection_id)
        if (
            connection is None or connection.provider_key != "whatsapp_evolution"
            or connection.status is not IntegrationStatus.ACTIVE
        ):
            raise PermissionError("evolution_connection_inactive")
        instance = connection.config.get("instance_name")
        if not isinstance(instance, str):
            raise PermissionError("evolution_instance_invalid")
        token = self._integrations.active_secret_ciphertexts(
            item.connection_id
        ).get("instance_token")
        if token is None:
            raise PermissionError("evolution_instance_secret_unavailable")
        sender_hash = hmac.new(
            self._pepper, f"{item.connection_id}:{item.sender}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not self._inbox.claim(
            channel_id=item.connection_id, message_id=item.message_id,
            sender_hash=sender_hash, message_type="text",
        ):
            return False
        context = TenantContext(
            tenant_id=connection.tenant_id, unit_id=connection.unit_id,
            credential_id="channel:" + item.connection_id,
        )
        try:
            conversation = self._assistant.get_or_create_external_conversation(
                context=context, channel=Channel.WHATSAPP,
                external_ref=f"wae:{item.connection_id}:{sender_hash}",
            )
            if conversation.status is ConversationStatus.HUMAN_HANDOFF:
                self._inbox.complete(
                    channel_id=item.connection_id, message_id=item.message_id,
                    outbound_id=None,
                )
            else:
                reply = self._assistant.send_message(
                    context=context,
                    conversation_id=conversation.conversation_id,
                    content=item.text,
                )
                # Recheck after potentially long AI execution: if the owner
                # paused/revoked the channel meanwhile, do not initiate send.
                latest = self._integrations.get_unscoped(item.connection_id)
                if (
                    latest is None or latest.status is not IntegrationStatus.ACTIVE
                    or latest.revision != connection.revision
                ):
                    raise PermissionError("evolution_connection_changed_during_processing")
                # A long model request may outlive the claim timeout.
                # Refuse provider send if another worker quarantined the job.
                if self._queue is not None:
                    self._queue.assert_claim_current(
                        connection_id=item.connection_id, message_id=item.message_id,
                        claim_generation=item.claim_generation,
                    )
                outbound_id = self._transport.send_text(
                    instance, instance_token=self._vault.decrypt(token),
                    recipient=item.sender, message=reply.content,
                )
                self._inbox.complete(
                    channel_id=item.connection_id, message_id=item.message_id,
                    outbound_id=outbound_id,
                )
        except Exception:  # quarantine unknown committed side effects
            self._inbox.mark_reconcile(
                channel_id=item.connection_id, message_id=item.message_id,
                error_code="evolution_worker_uncertain",
            )
            raise
        return True
