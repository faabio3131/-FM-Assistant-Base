"""OrquestraÃ§Ã£o universal do canal WhatsApp sobre o FM Assistant Base."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from .channels.whatsapp_meta import (
    AudioTranscriber,
    AudioTranscriptionUnavailable,
    MetaWhatsAppClient,
    UnavailableAudioTranscriber,
    WhatsAppDeliveryUncertain,
    WhatsAppProviderError,
)
from .domain import Channel, ConversationStatus, TenantContext
from .service import AssistantService
from .whatsapp_repository import WhatsAppChannelRepository, WhatsAppInboundRepository


@dataclass(frozen=True, kw_only=True)
class WhatsAppWebhookResult:
    processed: int = 0
    duplicates: int = 0
    failed: int = 0
    reconcile_required: int = 0


class WhatsAppRuntime:
    def __init__(
        self,
        *,
        channels: WhatsAppChannelRepository,
        inbound: WhatsAppInboundRepository,
        assistant: AssistantService,
        sender_pepper: str,
        audio_transcriber: AudioTranscriber | None = None,
    ) -> None:
        if not sender_pepper.strip():
            raise ValueError("sender_pepper_required")
        self._channels = channels
        self._inbound = inbound
        self._assistant = assistant
        self._sender_pepper = sender_pepper
        self._audio_transcriber = audio_transcriber or UnavailableAudioTranscriber()

    def _sender_hash(self, *, channel_id: str, sender: str) -> str:
        return hmac.new(
            self._sender_pepper.encode("utf-8"),
            f"{channel_id}:{sender}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify_challenge(
        self,
        *,
        channel_id: str,
        verify_token: str,
        challenge: str,
    ) -> str:
        config = self._channels.get_by_channel_id(channel_id)
        if config is None:
            raise LookupError("whatsapp_channel_not_found")
        return MetaWhatsAppClient(config).verify_challenge(
            verify_token=verify_token,
            challenge=challenge,
        )

    def process_webhook(
        self,
        *,
        channel_id: str,
        body: bytes,
        signature: str,
    ) -> WhatsAppWebhookResult:
        config = self._channels.get_by_channel_id(channel_id)
        if config is None:
            raise LookupError("whatsapp_channel_not_found")
        client = MetaWhatsAppClient(config)
        messages = client.parse_webhook(body=body, signature=signature)

        processed = 0
        duplicates = 0
        failed = 0
        reconcile_required = 0

        for incoming in messages:
            sender_hash = self._sender_hash(
                channel_id=channel_id,
                sender=incoming.sender,
            )
            claimed = self._inbound.claim(
                channel_id=channel_id,
                message_id=incoming.message_id,
                sender_hash=sender_hash,
                message_type=incoming.message_type,
            )
            if not claimed:
                duplicates += 1
                continue

            context = TenantContext(
                tenant_id=config.tenant_id,
                unit_id=config.unit_id,
                credential_id=f"channel:{channel_id}",
            )
            external_ref = f"wa:{channel_id}:{sender_hash}"
            try:
                conversation = self._assistant.get_or_create_external_conversation(
                    context=context,
                    channel=Channel.WHATSAPP,
                    external_ref=external_ref,
                )

                if conversation.status is ConversationStatus.HUMAN_HANDOFF:
                    self._inbound.complete(
                        channel_id=channel_id,
                        message_id=incoming.message_id,
                        outbound_id=None,
                    )
                    processed += 1
                    continue

                if incoming.message_type == "audio":
                    assert incoming.media_id is not None
                    content, mime_type = client.download_audio(
                        media_id=incoming.media_id,
                        declared_mime_type=incoming.mime_type,
                    )
                    try:
                        user_text = self._audio_transcriber.transcribe(
                            content=content,
                            mime_type=mime_type,
                        )
                    except AudioTranscriptionUnavailable:
                        self._assistant.handoff(
                            context=context,
                            conversation_id=conversation.conversation_id,
                            reason="audio_transcriber_unavailable",
                        )
                        try:
                            outbound_id = client.send_text(
                                recipient=incoming.sender,
                                text=(
                                    "Recebi seu Ã¡udio, mas este atendimento ainda nÃ£o "
                                    "possui transcriÃ§Ã£o automÃ¡tica configurada. "
                                    "Vou encaminhar a conversa para atendimento humano."
                                ),
                                correlation_id=incoming.message_id,
                            )
                        except WhatsAppDeliveryUncertain as exc:
                            self._inbound.mark_reconcile(
                                channel_id=channel_id,
                                message_id=incoming.message_id,
                                error_code=type(exc).__name__,
                            )
                            reconcile_required += 1
                            continue
                        except WhatsAppProviderError as exc:
                            self._inbound.mark_failed(
                                channel_id=channel_id,
                                message_id=incoming.message_id,
                                error_code=type(exc).__name__,
                            )
                            failed += 1
                            continue
                        self._inbound.complete(
                            channel_id=channel_id,
                            message_id=incoming.message_id,
                            outbound_id=outbound_id,
                        )
                        processed += 1
                        continue
                else:
                    user_text = (incoming.text or "").strip()

                reply = self._assistant.send_message(
                    context=context,
                    conversation_id=conversation.conversation_id,
                    content=user_text,
                )
                try:
                    outbound_id = client.send_text(
                        recipient=incoming.sender,
                        text=reply.content,
                        correlation_id=incoming.message_id,
                    )
                except WhatsAppDeliveryUncertain as exc:
                    self._inbound.mark_reconcile(
                        channel_id=channel_id,
                        message_id=incoming.message_id,
                        error_code=type(exc).__name__,
                    )
                    reconcile_required += 1
                    continue
                except WhatsAppProviderError as exc:
                    self._inbound.mark_failed(
                        channel_id=channel_id,
                        message_id=incoming.message_id,
                        error_code=type(exc).__name__,
                    )
                    failed += 1
                    continue

                self._inbound.complete(
                    channel_id=channel_id,
                    message_id=incoming.message_id,
                    outbound_id=outbound_id,
                )
                processed += 1
            except (LookupError, PermissionError, RuntimeError, ValueError) as exc:
                self._inbound.mark_failed(
                    channel_id=channel_id,
                    message_id=incoming.message_id,
                    error_code=type(exc).__name__,
                )
                failed += 1

        return WhatsAppWebhookResult(
            processed=processed,
            duplicates=duplicates,
            failed=failed,
            reconcile_required=reconcile_required,
        )

