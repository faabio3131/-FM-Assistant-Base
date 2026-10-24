"""Crash-safe, bounded inbound quarantine without replaying provider requests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from fm_assistant.whatsapp_repository import WhatsAppInboundRepository


def test_stale_processing_quarantined_once_with_tenant_scope(client, provision_credential):
    first = provision_credential(client, "recover-tenant", "unit-a")
    second = provision_credential(client, "recover-other", "unit-b")
    from fm_assistant.domain import TenantContext
    from fm_assistant.evolution_onboarding import EvolutionOnboarding
    from fm_assistant.integration import WHATSAPP_EVOLUTION_PROVIDER, IntegrationStatus

    repo = client.app.state.integration_repository
    tenant_a = TenantContext(
        tenant_id="recover-tenant", unit_id="unit-a", credential_id=first,
    )
    tenant_b = TenantContext(
        tenant_id="recover-other", unit_id="unit-b", credential_id=second,
    )
    a = repo.create_connection(
        tenant_a, provider=WHATSAPP_EVOLUTION_PROVIDER,
        config={"instance_name": "fm_" + "a" * 32},
        status=IntegrationStatus.DRAFT,
    )
    b = repo.create_connection(
        tenant_b, provider=WHATSAPP_EVOLUTION_PROVIDER,
        config={"instance_name": "fm_" + "b" * 32},
        status=IntegrationStatus.DRAFT,
    )
    inbox = WhatsAppInboundRepository(repo._session_factory)
    for channel in (a.connection_id, b.connection_id):
        assert inbox.claim(
            channel_id=channel, message_id="WA-CRASH",
            sender_hash="c" * 64, message_type="text",
        )
    engine = create_engine(client.app.state.settings.database_url)
    old = (datetime.now(UTC) - timedelta(minutes=12)).strftime("%Y-%m-%d %H:%M:%S.%f")
    with engine.begin() as db:
        db.execute(text(
            "UPDATE assistant_integration_inbound SET updated_at=:cutoff "
            "WHERE message_id='WA-CRASH'"
        ), {"cutoff": old})
    engine.dispose()
    from fm_assistant.channels.whatsapp_evolution import EvolutionClient, EvolutionSettings
    from fm_assistant.credential_vault import FernetCredentialVault

    onboarding = EvolutionOnboarding(
        repository=repo,
        vault=FernetCredentialVault(client.app.state.settings.channel_encryption_key),
        transport=EvolutionClient(EvolutionSettings(
            origin="https://example.test", global_key="g" * 40,
        )),
    )
    with pytest.raises(LookupError):
        onboarding.quarantine_stale(
            tenant_b, connection_id=a.connection_id, inbox=inbox,
        )
    assert onboarding.quarantine_stale(
        tenant_a, connection_id=a.connection_id, inbox=inbox,
    ) == 1
    assert inbox.status(channel_id=a.connection_id, message_id="WA-CRASH") == "reconcile_required"
    assert inbox.status(channel_id=b.connection_id, message_id="WA-CRASH") == "processing"
    assert onboarding.quarantine_stale(
        tenant_a, connection_id=a.connection_id, inbox=inbox,
    ) == 0
    assert inbox.claim(
        channel_id=a.connection_id, message_id="WA-CRASH",
        sender_hash="c" * 64, message_type="text",
    ) is False


def test_stale_quarantine_rejects_invalid_windows(client):
    from fm_assistant.domain import TenantContext
    from fm_assistant.evolution_onboarding import EvolutionOnboarding

    context = TenantContext(tenant_id="t", unit_id="u", credential_id="c")
    repository = client.app.state.integration_repository
    for bad in (-1, 0, 59, 86401, True):
        with pytest.raises(ValueError):
            EvolutionOnboarding.quarantine_stale(
                None, context, connection_id="invalid",
                inbox=WhatsAppInboundRepository(repository._session_factory),
                older_than_seconds=bad,
            )
