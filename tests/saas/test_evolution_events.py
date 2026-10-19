"""Standalone signed ingress protocol tests, independent of real VPS."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest

from fm_assistant.channels.evolution_events import (
    EvolutionEventDenied, EvolutionEventVerifier,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
CID = "feca847a-bdfa-4e67-9f88-5deca92c4e10"
KEY = "fm-ingress-synthetic-signing-key-" + "p" * 32


def _signed(payload, *, connection_id=CID, at=NOW):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    timestamp = str(int(at.timestamp()))
    canonical = (
        b"POST\n/webhooks/fm-evolution/" + connection_id.encode() +
        b"\n" + timestamp.encode() + b"\n" + raw
    )
    signature = hmac.new(KEY.encode(), canonical, hashlib.sha256).hexdigest()
    return raw, signature, timestamp


def _event():
    return {
        "event": "messages.upsert",
        "instance": "fm_" + "c" * 32,
        "data": [
            {"key": {
                "id": "WA-001", "fromMe": False,
                "remoteJid": "5511999999999@s.whatsapp.net",
            }, "message": {"conversation": "Oi"}},
            {"key": {
                "id": "WA-002", "fromMe": True,
                "remoteJid": "5511888888888@s.whatsapp.net",
            }, "message": {"conversation": "mensagem do bot"}},
        ],
    }


def test_exact_signed_webhook_filters_own_outbound_messages():
    raw, signature, timestamp = _signed(_event())
    verifier = EvolutionEventVerifier(signing_key=KEY)
    items = verifier.parse(
        connection_id=CID, expected_instance="fm_" + "c" * 32,
        raw=raw, signature=signature, timestamp=timestamp, now=NOW,
    )
    assert [(item.message_id, item.text) for item in items] == [("WA-001", "Oi")]
    assert items[0].sender == "5511999999999"


def test_webhook_rejects_unsigned_wrong_tenant_and_tampered_events():
    raw, signature, timestamp = _signed(_event())
    verifier = EvolutionEventVerifier(signing_key=KEY)
    probes = (
        (CID, "fm_" + "c" * 32, raw + b" ", signature, timestamp, NOW),
        (CID, "fm_" + "x" * 32, raw, signature, timestamp, NOW),
        ("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa", "fm_" + "c" * 32,
         raw, signature, timestamp, NOW),
        (CID, "fm_" + "c" * 32, raw, signature, timestamp, NOW + timedelta(minutes=5)),
        (CID, "fm_" + "c" * 32, raw, "x" * 64, timestamp, NOW),
    )
    for cid, instance, body, sig, ts, now in probes:
        with pytest.raises(EvolutionEventDenied, match="evolution_webhook_denied"):
            verifier.parse(
                connection_id=cid, expected_instance=instance, raw=body,
                signature=sig, timestamp=ts, now=now,
            )


def test_unsigned_origin_proposal_cannot_enable_webhooks():
    with pytest.raises(ValueError, match="evolution_event_signer_invalid"):
        EvolutionEventVerifier(signing_key="weak")
    verifier = EvolutionEventVerifier(signing_key=KEY)
    raw, signature, ts = _signed({"event": "connection.update", "instance": "fm_" + "c" * 32})
    assert verifier.parse(
        connection_id=CID, expected_instance="fm_" + "c" * 32,
        raw=raw, signature=signature, timestamp=ts, now=NOW,
    ) == ()
