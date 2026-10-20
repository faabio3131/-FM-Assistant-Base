"""FM-controlled native Evolution ingress, separate from the internal broker HMAC.

Evolution v2 per-instance webhook sends an FM-generated opaque credential in
a configured HTTPS header. The possession credential authenticates the sender
against the instance; it is not a provider-native digital signature.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from .credential_vault import CredentialVault
from .evolution_runtime import EvolutionDeliveryResult, EvolutionRuntime
from .integration import IntegrationStatus
from .integration_repository import IntegrationRepository


class NativeEvolutionDenied(ValueError):
    pass


class EvolutionNativeIngress:
    def __init__(
        self, *, repository: IntegrationRepository, vault: CredentialVault,
        runtime: EvolutionRuntime, internal_signer: str,
    ) -> None:
        if not isinstance(internal_signer, str) or len(internal_signer) < 32:
            raise ValueError("evolution_ingress_internal_signer_invalid")
        self._repository = repository
        self._vault = vault
        self._runtime = runtime
        self._signer = internal_signer.encode("utf-8")

    def receive(
        self, *, connection_id: str, token: str | None, raw: bytes,
    ) -> EvolutionDeliveryResult:
        if (
            not isinstance(token, str) or not 32 <= len(token) <= 256
            or not isinstance(raw, bytes) or not 1 <= len(raw) <= 65536
        ):
            raise NativeEvolutionDenied("evolution_native_denied")
        connection = self._repository.get_unscoped(connection_id)
        if (
            connection is None or connection.provider_key != "whatsapp_evolution"
            or connection.status is IntegrationStatus.REVOKED
        ):
            raise NativeEvolutionDenied("evolution_native_denied")
        encrypted = self._repository.active_secret_ciphertexts(
            connection_id
        ).get("native_webhook_token")
        if encrypted is None:
            raise NativeEvolutionDenied("evolution_native_denied")
        credential = self._vault.decrypt(encrypted)
        if not hmac.compare_digest(
            hashlib.sha256(token.encode()).digest(),
            hashlib.sha256(credential.encode()).digest(),
        ):
            raise NativeEvolutionDenied("evolution_native_denied")
        # A paused channel may accept provider status receipts solely for
        # reconciliation; never accept inbound messages or reopen events.
        if connection.status is IntegrationStatus.DISABLED:
            try:
                event = json.loads(raw)
            except (TypeError, ValueError) as exc:
                raise NativeEvolutionDenied("evolution_native_denied") from exc
            if not isinstance(event, dict) or event.get("event") != "messages.update":
                raise NativeEvolutionDenied("evolution_native_denied")
        # Forward the exact bytes through the EXISTING signed FM internal
        # contract after native authentication. Untrusted caller-controlled
        # HMAC/timestamp headers are never accepted as forwarding inputs.
        timestamp = str(int(time.time()))
        path = "/webhooks/fm-evolution/" + connection_id
        canonical = (
            b"POST\n" + path.encode() + b"\n" +
            timestamp.encode() + b"\n" + raw
        )
        digest = hmac.new(self._signer, canonical, hashlib.sha256).hexdigest()
        return self._runtime.receive(
            connection_id=connection_id, raw=raw,
            signature=digest, timestamp=timestamp,
        )
