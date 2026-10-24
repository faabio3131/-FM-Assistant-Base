"""Authenticated normalized Evolution ingress contract, before Assistant routing.

Only a trusted FM ingress broker can sign the canonical raw payload. Native
provider webhooks MUST NOT call this port without authenticated proxying.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime


class EvolutionEventDenied(ValueError):
    pass


@dataclass(frozen=True, kw_only=True)
class EvolutionInboundText:
    message_id: str
    sender: str
    text: str


class EvolutionEventVerifier:
    PATH_PREFIX = "/webhooks/fm-evolution/"

    def __init__(self, *, signing_key: str):
        if not isinstance(signing_key, str) or len(signing_key) < 32:
            raise ValueError("evolution_event_signer_invalid")
        self._key = signing_key.encode("utf-8")

    def parse(
        self, *, connection_id: str, expected_instance: str,
        raw: bytes, signature: str | None, timestamp: str | None,
        now: datetime,
    ) -> tuple[EvolutionInboundText, ...]:
        if (
            not isinstance(connection_id, str)
            or re.fullmatch(r"[0-9a-f-]{36}", connection_id) is None
            or not isinstance(raw, bytes) or len(raw) > 65536
            or not isinstance(signature, str)
            or re.fullmatch(r"[0-9a-f]{64}", signature) is None
            or not isinstance(timestamp, str) or not timestamp.isascii()
            or re.fullmatch(r"[0-9]{10}", timestamp) is None
            or now.tzinfo is None or now.utcoffset() is None
        ):
            raise EvolutionEventDenied("evolution_webhook_denied")
        if abs(int(now.astimezone(UTC).timestamp()) - int(timestamp)) > 60:
            raise EvolutionEventDenied("evolution_webhook_denied")
        path = self.PATH_PREFIX + connection_id
        canonical = b"POST\n" + path.encode() + b"\n" + timestamp.encode() + b"\n" + raw
        expected = hmac.new(self._key, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise EvolutionEventDenied("evolution_webhook_denied")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise EvolutionEventDenied("evolution_webhook_denied") from exc
        if not isinstance(payload, dict) or payload.get("instance") != expected_instance:
            raise EvolutionEventDenied("evolution_webhook_denied")
        if payload.get("event") not in {"messages.upsert", "connection.update"}:
            return ()
        if payload["event"] == "connection.update":
            return ()
        raw_data = payload.get("data")
        items = raw_data if isinstance(raw_data, list) else [raw_data]
        if len(items) > 32:
            raise EvolutionEventDenied("evolution_webhook_denied")
        messages: list[EvolutionInboundText] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if not isinstance(key, dict) or key.get("fromMe") is not False:
                continue
            message_id = key.get("id")
            jid = key.get("remoteJid")
            body = item.get("message")
            if not isinstance(body, dict):
                continue
            text = body.get("conversation")
            if not isinstance(text, str):
                extended = body.get("extendedTextMessage")
                text = extended.get("text") if isinstance(extended, dict) else None
            if (
                not isinstance(message_id, str)
                or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", message_id) is None
                or not isinstance(jid, str) or not jid.endswith("@s.whatsapp.net")
                or not isinstance(text, str) or not 1 <= len(text.strip()) <= 20000
            ):
                continue
            phone = jid.split("@", 1)[0]
            if not phone.isascii() or not phone.isdecimal() or not 8 <= len(phone) <= 20:
                continue
            messages.append(EvolutionInboundText(
                message_id=message_id, sender=phone, text=text.strip(),
            ))
        return tuple(messages)
