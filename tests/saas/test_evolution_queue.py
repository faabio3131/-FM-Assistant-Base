"""Durable encrypted async inbound queue, synthetic storage and worker tests."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from fm_assistant.credential_vault import FernetCredentialVault
from fm_assistant.domain import TenantContext
from fm_assistant.evolution_queue import EvolutionInboundQueue, EvolutionQueueCapacityExceeded
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


def test_two_workers_do_not_claim_same_pending_job(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    assert queue.enqueue(
        connection_id=cid, message_id="race-one",
        sender="5511999999999", text="One message",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: queue.claim(), range(2)))
    actual = [item for item in claimed if item is not None]
    assert len(actual) == 1
    assert actual[0].message_id == "race-one"
    assert queue.state(connection_id=cid, message_id="race-one") == "processing"
    queue.finish(connection_id=cid, message_id="race-one", reconciled=False)
    assert queue.claim() is None


def test_per_connection_backpressure_duplicate_and_review(client, provision_credential):
    cid, _q = _setup(client, provision_credential)
    repo = client.app.state.integration_repository
    vault = FernetCredentialVault(client.app.state.settings.channel_encryption_key)
    queue = EvolutionInboundQueue(repo._session_factory, vault, max_pending_per_connection=2)
    for message_id in ("capacity-1", "capacity-2"):
        assert queue.enqueue(
            connection_id=cid, message_id=message_id,
            sender="5511999999999", text="Mensagem protegida",
        )
    assert queue.enqueue(
        connection_id=cid, message_id="capacity-1",
        sender="5511999999999", text="Duplicata",
    ) is False
    with pytest.raises(EvolutionQueueCapacityExceeded):
        queue.enqueue(
            connection_id=cid, message_id="capacity-3",
            sender="5511999999999", text="Excedente",
        )
    snapshot = queue.operational_snapshot(connection_id=cid)
    assert snapshot["counts"]["pending"] == 2
    assert snapshot["capacity"] == 2
    assert "Mensagem protegida" not in str(snapshot)
    assert "5511999999999" not in str(snapshot)
    item = queue.claim()
    assert item is not None
    queue.finish(
        connection_id=cid, message_id=item.message_id,
        reconciled=True, code="manual_proof_needed",
    )
    assert queue.acknowledge_reconciliation(
        connection_id=cid, message_id=item.message_id,
    )
    assert queue.state(connection_id=cid, message_id=item.message_id) == "reviewed"
    assert queue.acknowledge_reconciliation(
        connection_id=cid, message_id=item.message_id,
    ) is False
    assert queue.enqueue(
        connection_id=cid, message_id="capacity-3",
        sender="5511999999999", text="Agora há espaço",
    )
    assert queue.enqueue(
        connection_id=cid, message_id=item.message_id,
        sender="5511999999999", text="Não reexecutar",
    ) is False


def test_operator_reconciliation_api_scope(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    foreign_key = provision_credential(client, "queue-foreign", "foreign-unit")
    own_key = client.post(
        "/v1/admin/credentials", headers={"X-Admin-Key": "admin-test-key"},
        json={"tenant_id": "queue-tenant", "unit_id": "queue-unit"},
    ).json()["api_key"]
    queue.enqueue(
        connection_id=cid, message_id="operator-1",
        sender="5511999999999", text="Privacidade",
    )
    assert queue.claim() is not None
    queue.finish(
        connection_id=cid, message_id="operator-1",
        reconciled=True, code="manual_proof_needed",
    )
    url = f"/v1/channels/whatsapp/qr/{cid}/operations"
    assert client.get(url).status_code == 401
    assert client.get(url,headers={"Authorization":f"Bearer {foreign_key}"}).status_code == 404
    response = client.get(url,headers={"Authorization":f"Bearer {own_key}"})
    assert response.status_code == 200, response.text
    assert "Privacidade" not in response.text
    assert response.json()["reconciliation"][0]["message_id"] == "operator-1"
    review = url + "/operator-1/review"
    assert client.post(review,headers={"Authorization":f"Bearer {foreign_key}"}).status_code == 404
    assert client.post(review,headers={"Authorization":f"Bearer {own_key}"}).status_code == 200
    assert client.post(review,headers={"Authorization":f"Bearer {own_key}"}).status_code == 409


def test_worker_claim_freshness_refuses_stale_and_quarantined(
    client, provision_credential,
):
    cid, queue = _setup(client, provision_credential)
    queue.enqueue(
        connection_id=cid, message_id="expired-lease",
        sender="5511999999999", text="Never auto-resend",
    )
    item = queue.claim()
    assert item is not None
    queue.assert_claim_current(connection_id=cid, message_id=item.message_id)
    engine = create_engine(client.app.state.settings.database_url)
    with engine.begin() as db:
        db.execute(text(
            "UPDATE assistant_evolution_inbound_jobs SET claimed_at=:old "
            "WHERE connection_id=:cid AND message_id=:mid"
        ), {
            "old": (datetime.now(UTC)-timedelta(minutes=10)).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            ), "cid": cid, "mid": item.message_id,
        })
    engine.dispose()
    with pytest.raises(RuntimeError, match="evolution_claim_expired_or_revoked"):
        queue.assert_claim_current(connection_id=cid, message_id=item.message_id)
    assert queue.quarantine_stale() == 1
    with pytest.raises(RuntimeError, match="evolution_claim_expired_or_revoked"):
        queue.assert_claim_current(connection_id=cid, message_id=item.message_id)
    assert queue.claim() is None


def test_queue_operational_snapshot_includes_age_without_private_data(
    client, provision_credential,
):
    cid, queue = _setup(client, provision_credential)
    assert queue.enqueue(
        connection_id=cid, message_id="age-sample",
        sender="5511988888888", text="Private payload sentinel",
    )
    overview = queue.operational_snapshot(connection_id=cid)
    assert overview["oldest_age_seconds"]["pending"] >= 0
    assert "5511988888888" not in str(overview)
    assert "Private payload sentinel" not in str(overview)


def test_claim_generation_rejects_foreign_renewal_and_completion(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    assert queue.enqueue(
        connection_id=cid, message_id="generation-1",
        sender="5511999999999", text="Privado",
    )
    item = queue.claim()
    assert item is not None
    assert item.claim_generation >= 1
    with pytest.raises(RuntimeError, match="evolution_claim_expired_or_revoked"):
        queue.renew_claim(
            connection_id=cid, message_id=item.message_id,
            claim_generation=item.claim_generation + 1,
        )
    with pytest.raises(RuntimeError, match="evolution_job_state_conflict"):
        queue.finish(
            connection_id=cid, message_id=item.message_id, reconciled=False,
            claim_generation=item.claim_generation + 1,
        )
    assert queue.state(connection_id=cid, message_id=item.message_id) == "processing"
    queue.renew_claim(
        connection_id=cid, message_id=item.message_id,
        claim_generation=item.claim_generation,
    )
    queue.assert_claim_current(
        connection_id=cid, message_id=item.message_id,
        claim_generation=item.claim_generation,
    )
    queue.finish(
        connection_id=cid, message_id=item.message_id, reconciled=False,
        claim_generation=item.claim_generation,
    )
    with pytest.raises(RuntimeError, match="evolution_claim_expired_or_revoked"):
        queue.renew_claim(
            connection_id=cid, message_id=item.message_id,
            claim_generation=item.claim_generation,
        )


def test_expired_generation_cannot_be_renewed(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    queue.enqueue(
        connection_id=cid, message_id="generation-expired",
        sender="5511999999999", text="Confidencial",
    )
    item = queue.claim()
    assert item is not None
    engine = create_engine(client.app.state.settings.database_url)
    with engine.begin() as db:
        db.execute(text(
            "UPDATE assistant_evolution_inbound_jobs SET claimed_at=:old "
            "WHERE connection_id=:cid AND message_id=:mid"
        ), {
            "old": (datetime.now(UTC) - timedelta(minutes=10)).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            ),
            "cid": cid, "mid": item.message_id,
        })
    engine.dispose()
    with pytest.raises(RuntimeError, match="evolution_claim_expired_or_revoked"):
        queue.renew_claim(
            connection_id=cid, message_id=item.message_id,
            claim_generation=item.claim_generation,
        )
    assert queue.quarantine_stale() == 1
    assert queue.state(connection_id=cid, message_id=item.message_id) == "reconcile_required"


def test_outbound_intent_is_durable_and_not_replayable(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    queue.enqueue(
        connection_id=cid, message_id="outbound-first",
        sender="5511999999999", text="Secret content",
    )
    item = queue.claim()
    assert item is not None
    operation = queue.begin_outbound(
        connection_id=cid, message_id=item.message_id,
        claim_generation=item.claim_generation,
    )
    assert operation
    assert queue.state(connection_id=cid, message_id=item.message_id) == "sending"
    with pytest.raises(RuntimeError, match="evolution_outbound_intent_conflict"):
        queue.begin_outbound(
            connection_id=cid, message_id=item.message_id,
            claim_generation=item.claim_generation,
        )
    with pytest.raises(RuntimeError, match="evolution_outbound_result_conflict"):
        queue.record_outbound_result(
            connection_id=cid, message_id=item.message_id,
            claim_generation=item.claim_generation, operation_id="forged",
            outbound_reference="evolution-ack",
        )
    queue.record_outbound_result(
        connection_id=cid, message_id=item.message_id,
        claim_generation=item.claim_generation, operation_id=operation,
        outbound_reference="evolution-ack",
    )
    queue.finish(
        connection_id=cid, message_id=item.message_id, reconciled=False,
        claim_generation=item.claim_generation,
    )
    assert queue.state(connection_id=cid, message_id=item.message_id) == "complete"
    assert queue.enqueue(
        connection_id=cid, message_id=item.message_id,
        sender="5511999999999", text="Replay",
    ) is False
    assert queue.claim() is None


def test_crashed_outbound_goes_to_manual_reconciliation_without_resend(
    client, provision_credential,
):
    cid, queue = _setup(client, provision_credential)
    queue.enqueue(
        connection_id=cid, message_id="send-unknown",
        sender="5511999999999", text="Sensitive",
    )
    item = queue.claim()
    assert item is not None
    operation = queue.begin_outbound(
        connection_id=cid, message_id=item.message_id,
        claim_generation=item.claim_generation,
    )
    engine = create_engine(client.app.state.settings.database_url)
    with engine.begin() as db:
        db.execute(text(
            "UPDATE assistant_evolution_inbound_jobs SET claimed_at=:old "
            "WHERE connection_id=:cid AND message_id=:mid"
        ), {
            "old": (datetime.now(UTC) - timedelta(minutes=10)).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            ), "cid": cid, "mid": item.message_id,
        })
    engine.dispose()
    assert queue.quarantine_stale() == 1
    assert queue.state(connection_id=cid, message_id=item.message_id) == "reconcile_required"
    snapshot = queue.operational_snapshot(connection_id=cid)
    reviewed = snapshot["reconciliation"][0]
    assert reviewed["outbound_status"] == "uncertain"
    assert reviewed["outbound_operation_id"] == operation
    assert "Sensitive" not in str(snapshot)
    assert "5511999999999" not in str(snapshot)
    assert queue.claim() is None
    assert queue.acknowledge_reconciliation(
        connection_id=cid, message_id=item.message_id,
    )
    assert queue.enqueue(
        connection_id=cid, message_id=item.message_id,
        sender="5511999999999", text="Resend forbidden",
    ) is False


def test_concurrent_outbound_intent_has_single_winner(client, provision_credential):
    cid, queue = _setup(client, provision_credential)
    queue.enqueue(
        connection_id=cid, message_id="send-race",
        sender="5511999999999", text="Race",
    )
    item = queue.claim()
    assert item is not None

    def attempt(_):
        try:
            return queue.begin_outbound(
                connection_id=cid, message_id=item.message_id,
                claim_generation=item.claim_generation,
            )
        except Exception as exc:  # noqa: BLE001 - concurrency probe records DB lock failures
            return type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    winners = [result for result in results if isinstance(result, str) and len(result) == 32]
    assert len(winners) == 1
    assert queue.state(connection_id=cid, message_id=item.message_id) == "sending"
