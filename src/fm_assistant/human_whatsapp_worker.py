"""F5 queue worker for operator-initiated WhatsApp outbound messages."""
from __future__ import annotations

import time

from .channels.whatsapp_evolution import EvolutionClient, EvolutionSettings
from .credential_vault import FernetCredentialVault
from .db import create_session_factory
from .human_whatsapp_outbox import HumanWhatsAppOutbox
from .integration_repository import IntegrationRepository
from .settings import load_settings


def main() -> int:
    settings = load_settings()
    if not settings.evolution_origin or not settings.evolution_global_key:
        raise RuntimeError("human_outbox.evolution_not_configured")
    engine, sessions = create_session_factory(settings.database_url)
    outbox = HumanWhatsAppOutbox(
        sessions, FernetCredentialVault(settings.channel_encryption_key),
        sender_pepper=settings.credential_pepper,
    )
    transport = EvolutionClient(EvolutionSettings(
        origin=settings.evolution_origin, global_key=settings.evolution_global_key,
    ))
    integrations = IntegrationRepository(sessions)
    try:
        while True:
            processed = outbox.process_one(integrations=integrations, transport=transport)
            if processed is None:
                time.sleep(2)
    except KeyboardInterrupt:
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
