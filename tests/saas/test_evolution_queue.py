"""Durable encrypted async inbound queue, synthetic storage and worker tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from fm_assistant.credential_vault import FernetCredentialVault
from fm_assistant.db import EvolutionInboundJobORM
from fm_assistant.domain import TenantContext
from fm_assistant.evolution_queue import EvolutionInboundQueue
from fm_assistant.integration import WHATSAPP_EVOLUTION_PROVIDER, IntegrationStatus


def _setup(client, provision_credential):
    key = provision_credential(client, "queue-tenant", "queue-unit")
    ctx = TenantContext(tenant_id="queue-tenant", unit_id="queue-unit", credential_id=key)
    repo = client.app.state.integration_repository
    conn = repo.create_connection(
        ctx, provider=WHATSAPP_EVOLUTION_PROVIDER,
        config={"instance_name": "fm_" + "a" * 32},
        status=IntegrationStatus.ACTIVE,
    )
    q = EvolutionInboundQueue(
        repo._session_factory,
        FernetCredentialVault(client.app.state.settings.channel_encryption_key),
    )
    return conn.connection_id, q


def test_encrypted_queue_claim_once_and_purge_plaintext(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    assert queue.enqueue(
        connection_id=cid, message_id="m1",
        sender="5511999999999", text="Dados privados de conversa",
    )
    assert queue.enqueue(
        connection_id=cid, message_id="m1",
        sender="5511999999999", text="Dados privados de conversa",
    ) is False
    engine = create_engine(client.app.state.settings.database_url)
    with engine.connect() as db:
        raw = db.execute(text(
            "SELECT ciphertext FROM assistant_evolution_inbound_jobs "
            "WHERE connection_id=:cid AND message_id='m1'"
        ), {"cid":cid}).scalar_one()
        assert "5511999999999" not in raw
        assert "Dados privados" not in raw
    job = queue.claim()
    assert job is not None
    assert job.connection_id == cid
    assert job.sender == "5511999999999"
    assert job.text == "Dados privados de conversa"
    assert queue.claim() is None
    queue.finish(connection_id=cid, message_id="m1", reconciled=False)
    assert queue.state(connection_id=cid, message_id="m1") == "complete"
    with engine.connect() as db:
        assert db.execute(text(
            "SELECT ciphertext FROM assistant_evolution_inbound_jobs "
            "WHERE connection_id=:cid AND message_id='m1'"
        ), {"cid":cid}).scalar_one() == ""
    engine.dispose()


def test_stranded_lease_quarantined_without_requeue(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    assert queue.enqueue(
        connection_id=cid, message_id="m2", sender="5511999999999", text="Olá",
    )
    assert queue.claim() is not None
    engine = create_engine(client.app.state.settings.database_url)
    with engine.begin() as db:
        db.execute(text(
            "UPDATE assistant_evolution_inbound_jobs SET claimed_at=:old "
            "WHERE connection_id=:cid"
        ), {
            "old":(datetime.now(UTC)-timedelta(minutes=10)).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            ),"cid":cid,
        })
    engine.dispose()
    assert queue.quarantine_stale(older_than_seconds=300) == 1
    assert queue.state(connection_id=cid,message_id="m2") == "reconcile_required"
    assert queue.claim() is None
    assert queue.quarantine_stale(older_than_seconds=300) == 0
    assert queue.enqueue(
        connection_id=cid,message_id="m2",sender="5511999999999",text="Olá",
    ) is False


def test_queue_refuses_invalid_worker_controls(client, provision_credential):
    _cid, queue = _setup(client, provision_credential)
    for limit in (0, 501, True):
        with pytest.raises(ValueError):
            queue.quarantine_stale(limit=limit)
    for window in (0, 59, 86401, True):
        with pytest.raises(ValueError):
            queue.quarantine_stale(older_than_seconds=window)
