"""Adapter universal para WhatsApp Cloud API (Meta).

Sem imports de Kordena ou de qualquer domínio vertical.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class WhatsAppProviderError(RuntimeError):
    """Falha sanitizada e definitiva do provedor."""


class WhatsAppDeliveryUncertain(WhatsAppProviderError):
    """O POST pode ter sido processado; reenvio cego é proibido."""


class AudioTranscriptionUnavailable(RuntimeError):
    """Não existe transcriber configurado para áudio."""


@dataclass(frozen=True, kw_only=True)
class WhatsAppMetaConfig:
    channel_id: str
    tenant_id: str
    unit_id: str
    phone_number_id: str
    business_account_id: str | None
    access_token: str
    app_secret: str
    verify_token: str
    graph_api_version: str = "v23.0"
    timeout_seconds: float = 8.0

    def __post_init__(self) -> None:
        required = (
            self.channel_id,
            self.tenant_id,
            self.unit_id,
            self.phone_number_id,
            self.access_token,
            self.app_secret,
            self.verify_token,
        )
        if not all(value.strip() for value in required):
            raise ValueError("whatsapp_meta_config_incomplete")
        if not self.graph_api_version.startswith("v"):
            raise ValueError("whatsapp_meta_graph_version_invalid")


@dataclass(frozen=True, kw_only=True)
class WhatsAppInboundMessage:
    message_id: str
    sender: str
    message_type: str
    timestamp: str
    text: str | None = None
    media_id: str | None = None
    mime_type: str | None = None

    def __post_init__(self) -> None:
        if not self.message_id.strip() or not self.sender.strip():
            raise ValueError("whatsapp_message_invalid")
        if self.message_type == "text" and not (self.text or "").strip():
            raise ValueError("whatsapp_text_empty")
        if self.message_type == "audio" and not (self.media_id or "").strip():
            raise ValueError("whatsapp_audio_missing_media")


class AudioTranscriber(Protocol):
    def transcribe(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        correlation_id: str,
        content: bytes,
        mime_type: str,
    ) -> str: ...


class UnavailableAudioTranscriber:
    def transcribe(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        correlation_id: str,
        content: bytes,
        mime_type: str,
    ) -> str:
        del tenant_id, unit_id, correlation_id, content, mime_type
        raise AudioTranscriptionUnavailable("audio_transcriber_unavailable")


class MetaWhatsAppClient:
    def __init__(self, config: WhatsAppMetaConfig) -> None:
        self._config = config

    def verify_challenge(self, *, verify_token: str, challenge: str) -> str:
        if not hmac.compare_digest(self._config.verify_token, verify_token):
            raise WhatsAppProviderError("meta_verify_token_invalid")
        return challenge

    def validate_signature(self, *, body: bytes, signature: str) -> bool:
        received = signature.removeprefix("sha256=").strip().casefold()
        expected = hmac.new(
            self._config.app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return bool(received) and hmac.compare_digest(expected, received)

    def parse_webhook(
        self,
        *,
        body: bytes,
        signature: str,
    ) -> tuple[WhatsAppInboundMessage, ...]:
        if not self.validate_signature(body=body, signature=signature):
            raise WhatsAppProviderError("meta_signature_invalid")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WhatsAppProviderError("meta_webhook_invalid") from exc
        if not isinstance(payload, Mapping):
            raise WhatsAppProviderError("meta_webhook_invalid")

        messages: list[WhatsAppInboundMessage] = []
        entries = payload.get("entry")
        if not isinstance(entries, list):
            return ()
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            changes = entry.get("changes")
            if not isinstance(changes, list):
                continue
            for change in changes:
                if not isinstance(change, Mapping):
                    continue
                value = change.get("value")
                if not isinstance(value, Mapping):
                    continue
                items = value.get("messages")
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, Mapping):
                        continue
                    message_id = str(item.get("id", "")).strip()
                    sender = str(item.get("from", "")).strip()
                    message_type = str(item.get("type", "")).strip().casefold()
                    timestamp = str(item.get("timestamp", "")).strip()
                    if not message_id or not sender or message_type not in {"text", "audio"}:
                        continue
                    text: str | None = None
                    media_id: str | None = None
                    mime_type: str | None = None
                    if message_type == "text":
                        raw_text = item.get("text")
                        if isinstance(raw_text, Mapping):
                            text = str(raw_text.get("body", "")).strip() or None
                    else:
                        raw_audio = item.get("audio")
                        if isinstance(raw_audio, Mapping):
                            media_id = str(raw_audio.get("id", "")).strip() or None
                            mime_type = str(raw_audio.get("mime_type", "")).strip() or None
                    try:
                        messages.append(
                            WhatsAppInboundMessage(
                                message_id=message_id,
                                sender=sender,
                                message_type=message_type,
                                timestamp=timestamp,
                                text=text,
                                media_id=media_id,
                                mime_type=mime_type,
                            )
                        )
                    except ValueError:
                        continue
        return tuple(messages)

    def parse_delivery_statuses(
        self, *, body: bytes, signature: str,
    ) -> tuple[tuple[str, str], ...]:
        """Only a valid Meta HMAC and matching phone_number_id can update state."""
        if not self.validate_signature(body=body, signature=signature):
            raise WhatsAppProviderError("meta_signature_invalid")
        if len(body) > 256_000:
            raise WhatsAppProviderError("meta_status_payload_too_large")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise WhatsAppProviderError("meta_webhook_invalid") from exc
        if not isinstance(payload, Mapping):
            raise WhatsAppProviderError("meta_webhook_invalid")
        entries = payload.get("entry", [])
        if not isinstance(entries, list) or len(entries) > 100:
            raise WhatsAppProviderError("meta_status_payload_invalid")
        results: list[tuple[str, str]] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            changes = entry.get("changes", [])
            if not isinstance(changes, list) or len(changes) > 50:
                raise WhatsAppProviderError("meta_status_payload_invalid")
            for change in changes:
                if not isinstance(change, Mapping):
                    continue
                value = change.get("value")
                if not isinstance(value, Mapping):
                    continue
                metadata = value.get("metadata")
                if not isinstance(metadata, Mapping) or str(
                    metadata.get("phone_number_id", "")
                ) != self._config.phone_number_id:
                    continue
                statuses = value.get("statuses", [])
                if not isinstance(statuses, list) or len(statuses) > 200:
                    raise WhatsAppProviderError("meta_status_payload_invalid")
                for item in statuses:
                    if not isinstance(item, Mapping):
                        continue
                    reference = item.get("id")
                    state = item.get("status")
                    if (
                        isinstance(reference, str) and 1 <= len(reference) <= 160
                        and isinstance(state, str)
                        and state in {"sent", "delivered", "read"}
                    ):
                        results.append((reference, state))
        return tuple(results)

    def send_text(
        self,
        *,
        recipient: str,
        text: str,
        correlation_id: str,
    ) -> str:
        destination = "".join(ch for ch in recipient if ch.isdigit())
        body = text.strip()
        if not destination or not body:
            raise WhatsAppProviderError("whatsapp_outbound_incomplete")
        url = (
            f"https://graph.facebook.com/{self._config.graph_api_version}/"
            f"{self._config.phone_number_id}/messages"
        )
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": destination,
            "type": "text",
            "text": {"preview_url": False, "body": body},
            "biz_opaque_callback_data": correlation_id[:128],
        }
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._config.access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._config.timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise WhatsAppDeliveryUncertain("meta_delivery_uncertain") from exc

        if response.status_code >= 500 or response.status_code in {408, 429}:
            raise WhatsAppDeliveryUncertain(
                f"meta_delivery_uncertain_http_{response.status_code}"
            )
        if not 200 <= response.status_code < 300:
            raise WhatsAppProviderError(f"meta_rejected_http_{response.status_code}")
        try:
            data = response.json()
            outbound_id = str(data["messages"][0]["id"]).strip()
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise WhatsAppDeliveryUncertain("meta_outbound_id_missing") from exc
        if not outbound_id:
            raise WhatsAppDeliveryUncertain("meta_outbound_id_missing")
        return outbound_id

    def download_audio(
        self,
        *,
        media_id: str,
        declared_mime_type: str | None,
        max_bytes: int = 20 * 1024 * 1024,
    ) -> tuple[bytes, str]:
        media = media_id.strip()
        if not media:
            raise WhatsAppProviderError("whatsapp_audio_missing_media")
        metadata_url = (
            f"https://graph.facebook.com/{self._config.graph_api_version}/{media}"
        )
        headers = {"Authorization": f"Bearer {self._config.access_token}"}
        try:
            metadata_response = httpx.get(
                metadata_url,
                headers=headers,
                timeout=self._config.timeout_seconds,
            )
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            raise WhatsAppProviderError("meta_audio_metadata_failed") from exc

        url = str(metadata.get("url", "")).strip()
        mime_type = str(metadata.get("mime_type") or declared_mime_type or "").strip()
        try:
            file_size = int(metadata.get("file_size") or 0)
        except (TypeError, ValueError) as exc:
            raise WhatsAppProviderError("meta_audio_size_invalid") from exc
        if not url.startswith("https://") or not mime_type.casefold().startswith("audio/"):
            raise WhatsAppProviderError("meta_audio_not_authorized")
        if file_size < 0 or file_size > max_bytes:
            raise WhatsAppProviderError("meta_audio_too_large")

        try:
            audio_response = httpx.get(
                url,
                headers=headers,
                timeout=self._config.timeout_seconds,
            )
            audio_response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise WhatsAppProviderError("meta_audio_download_failed") from exc
        content = audio_response.content
        content_type = (
            audio_response.headers.get("content-type", mime_type).split(";", 1)[0].strip()
        )
        if not content or len(content) > max_bytes or not content_type.startswith("audio/"):
            raise WhatsAppProviderError("meta_audio_invalid")
        return content, content_type
