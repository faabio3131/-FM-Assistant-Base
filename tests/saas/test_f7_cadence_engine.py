"""F7 durable cadence engine: API authorization, task execution and recovery."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_identity_rbac import _bootstrap, _login

from fm_assistant.crm_workflow import CRMActivityORM
from fm_assistant.followup_cadences import CadenceJobORM


def _setup(client):
    _bootstrap(client)
    _login(client)
    contact = client.post("/v1/crm/contacts", json={"name": "Cliente CRM"})
    assert contact.status_code == 201, contact.text
    cid = contact.json()["contact_id"]
    opp = client.post("/v1/crm/opportunities", json={
        "contact_id": cid, "title": "Contrato anual", "amount_cents": 25000,
    })
    assert opp.status_code == 201, opp.text
    oid = opp.json()["opportunity_id"]
    p = client.put(f"/v1/followups/contacts/{cid}/preferences", json={
        "channel": "whatsapp", "expected_revision": 0,
        "opted_out": False, "timezone": "America/Sao_Paulo",
        "quiet_start": "22:00", "quiet_end": "08:00",
    })
    assert p.status_code == 200, p.text
    cadence = client.post("/v1/followups/cadences", json={
        "name": "Acompanhamento da proposta", "channel": "whatsapp",
        "steps": [
            {"delay_minutes": 0, "task": "Contatar sobre orçamento sigiloso"},
            {"delay_minutes": 60, "task": "Revisar resposta pendente"},
        ],
    })
    assert cadence.status_code == 201, cadence.text
    return cid, oid, cadence.json()


def _plan(client, cid, oid, cadence, *, key="f7-safe-example-0001", start=None):
    start = start or datetime.now(UTC)
    return client.post("/v1/followups/runs", json={
        "cadence_id": cadence["cadence_id"], "version": cadence["version"],
        "contact_id": cid, "opportunity_id": oid,
        "idempotency_key": key, "start_at": start.isoformat(),
    })


def test_schedule_idempotent_execution_and_encrypted_single_activity(client):
    cid, oid, cadence = _setup(client)
    start = datetime.now(UTC)
    created = _plan(client, cid, oid, cadence, start=start)
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["status"] == "active"
    assert len(run["jobs"]) == 2
    replay = _plan(client, cid, oid, cadence, start=start)
    assert replay.status_code == 201, replay.text
    assert replay.json()["run_id"] == run["run_id"]
    bad = _plan(client, cid, oid, cadence, start=start,
                key="f7-safe-example-0002")
    assert bad.status_code == 201
    mismatch = client.post("/v1/followups/runs", json={
        "cadence_id": cadence["cadence_id"], "version": 1,
        "contact_id": cid, "opportunity_id": oid,
        "idempotency_key": "f7-safe-example-0001",
        "start_at": (start + timedelta(seconds=1)).isoformat(),
    })
    assert mismatch.status_code == 409
    engine = client.app.state.cadence_engine
    when = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
    # Existing schedule is current relative to real test clock; move an
    # isolated run's due time backward for deterministic simulated worker time.
    with engine._sessions.begin() as db:
        for j in db.scalars(select(CadenceJobORM).where(
            CadenceJobORM.run_id == run["run_id"],
        )).all():
            j.due_at = when - timedelta(minutes=1) + timedelta(hours=j.step_index)
            j.available_at = j.due_at
    claim = engine.claim(now=when)
    assert claim is not None
    jid, generation = claim
    assert generation == 1
    assert engine.execute(jid, generation, now=when) == "completed"
    with pytest.raises(ValueError, match="cadence.lease_expired_or_fenced"):
        engine.execute(jid, generation, now=when)
    with engine._sessions() as db:
        activities = db.scalars(select(CRMActivityORM).where(
            CRMActivityORM.related_id == jid,
        )).all()
        assert len(activities) == 1
        assert activities[0].kind == "task"
        assert "orçamento sigiloso" not in activities[0].details_ciphertext
    timeline = client.get(f"/v1/crm/opportunities/{oid}/activities")
    assert timeline.status_code == 200
    assert "orçamento sigiloso" in timeline.text
    events = client.get(f"/v1/followups/runs/{run['run_id']}/events")
    assert events.status_code == 200
    assert [e["action"] for e in events.json()["items"]].count("completed") == 1
    assert "orçamento sigiloso" not in events.text


def test_quiet_hours_defer_and_live_opt_out_blocks(client):
    cid, oid, cadence = _setup(client)
    run = _plan(client, cid, oid, cadence).json()
    engine = client.app.state.cadence_engine
    midnight = datetime(2026, 10, 24, 1, 0, tzinfo=UTC)  # 22h Sao Paulo
    with engine._sessions.begin() as db:
        for job in db.scalars(select(CadenceJobORM).where(
            CadenceJobORM.run_id == run["run_id"],
        )).all():
            job.due_at = midnight - timedelta(minutes=1)
            job.available_at = job.due_at
    first = engine.claim(now=midnight)
    assert first
    assert engine.execute(*first, now=midnight) == "quiet_deferred"
    assert engine.claim(now=midnight) is None
    p = client.put(f"/v1/followups/contacts/{cid}/preferences", json={
        "channel": "whatsapp", "expected_revision": 1,
        "opted_out": True, "timezone": "America/Sao_Paulo",
        "quiet_start": "22:00", "quiet_end": "08:00",
    })
    assert p.status_code == 200, p.text
    later = midnight + timedelta(minutes=16)
    second = engine.claim(now=later)
    assert second
    assert engine.execute(*second, now=later) == "blocked"
    assert client.get(f"/v1/followups/runs/{run['run_id']}").json()["jobs"][0][
        "state"] == "blocked"
    with engine._sessions() as db:
        assert not db.scalars(select(CRMActivityORM).where(
            CRMActivityORM.related_id == second[0],
        )).all()


def test_expired_lease_recovery_backoff_and_dead_letter(client):
    cid, oid, cadence = _setup(client)
    run = _plan(client, cid, oid, cadence).json()
    engine = client.app.state.cadence_engine
    anchor = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
    with engine._sessions.begin() as db:
        job = db.get(CadenceJobORM, run["jobs"][0]["job_id"])
        job.due_at = anchor
        job.available_at = anchor
    one = engine.claim(now=anchor)
    assert one
    assert engine.recover(now=anchor + timedelta(seconds=121)) == 1
    with pytest.raises(ValueError, match="cadence.lease_expired_or_fenced"):
        engine.execute(*one, now=anchor + timedelta(seconds=122))
    assert engine.claim(now=anchor + timedelta(seconds=122)) is None
    two = engine.claim(now=anchor + timedelta(seconds=181))
    assert two and two[1] == one[1] + 1
    assert engine.fail(*two, code="internal_transient",
                       now=anchor + timedelta(seconds=181)) == "pending"
    assert engine.claim(now=anchor + timedelta(seconds=181)) is None
    three = engine.claim(now=anchor + timedelta(seconds=482))
    assert three and three[1] == 3
    assert engine.fail(*three, code="internal_transient",
                       now=anchor + timedelta(seconds=482)) == "dead"
    assert engine.recover(now=anchor + timedelta(days=1)) == 0
    dead = client.get(f"/v1/followups/runs/{run['run_id']}").json()["jobs"][0]
    assert dead["state"] == "dead"
    assert dead["attempt_count"] == 3
    assert dead["last_error"] == "internal_transient"
    assert engine.claim(now=anchor + timedelta(days=1)) is not None  # 2nd step.


def test_cancel_fences_lease_and_scoped_reads(client):
    cid, oid, cadence = _setup(client)
    run = _plan(client, cid, oid, cadence).json()
    rid = run["run_id"]
    engine = client.app.state.cadence_engine
    anchor = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
    with engine._sessions.begin() as db:
        job = db.get(CadenceJobORM, run["jobs"][0]["job_id"])
        job.available_at = anchor
    claimed = engine.claim(now=anchor)
    assert claimed
    canceled = client.post(f"/v1/followups/runs/{rid}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "cancelled"
    with pytest.raises(ValueError, match="cadence.lease_expired_or_fenced"):
        engine.execute(*claimed, now=anchor)
    assert engine.claim(now=anchor + timedelta(days=1)) is None
    assert client.get(f"/v1/followups/runs/{rid}/events").status_code == 200
    assert client.post(f"/v1/followups/runs/{rid}/cancel", headers={
        "Origin": "https://invalid.example",
    }).status_code == 403
    assert client.post("/v1/units", json={
        "unit_id": "branch", "display_name": "Filial",
    }).status_code == 200
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "branch",
    }).status_code == 200
    assert client.get(f"/v1/followups/runs/{rid}").status_code == 404
    assert client.get(f"/v1/followups/runs/{rid}/events").status_code == 404
    assert client.post(f"/v1/followups/runs/{rid}/cancel").status_code == 404


def test_version_immutability_and_scope_not_found(client):
    cid, oid, cadence = _setup(client)
    r = client.post("/v1/followups/cadences", json={
        "cadence_id": cadence["cadence_id"], "expected_version": 1,
        "name": "Acompanhamento atualizado", "channel": "whatsapp",
        "steps": [{"delay_minutes": 0, "task": "Solicitar confirmação"}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2
    assert len(client.get("/v1/followups/cadences").json()["items"]) == 2
    invalid = client.post("/v1/followups/cadences", json={
        "cadence_id": cadence["cadence_id"], "expected_version": 1,
        "name": "Concorrente", "channel": "whatsapp",
        "steps": [{"delay_minutes": 0, "task": "Não criar"}],
    })
    assert invalid.status_code == 409
    assert _plan(client, cid, oid, cadence).status_code == 201
    assert client.post("/v1/followups/cadences", json={
        "name": "Incorreta", "channel": "whatsapp",
        "steps": [
            {"delay_minutes": 5, "task": "a"},
            {"delay_minutes": 2, "task": "b"},
        ],
    }).status_code == 409
