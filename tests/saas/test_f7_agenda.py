"""F7 agenda: booked slots, revisions, scoped reads and atomic CRM reminders."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from test_f7_cadence_engine import _setup

from fm_assistant.agenda import AgendaAppointmentORM
from fm_assistant.crm_workflow import CRMActivityORM


def _book(client, contact, opportunity, start, *, key="f7-agenda-0001",
          title="Encontro reservado"):
    return client.post("/v1/followups/agenda", json={
        "contact_id": contact, "opportunity_id": opportunity,
        "title": title, "starts_at": start.isoformat(),
        "duration_minutes": 60, "remind_minutes": 90, "idempotency_key": key,
    })


def _window(start, hours=8):
    return {"start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=hours)).isoformat()}


def test_book_list_slot_conflict_and_idempotency(client):
    cid, oid, _ = _setup(client)
    start = (datetime.now(UTC) + timedelta(days=2)).replace(
        hour=13, minute=0, second=0, microsecond=0,
    )
    response = _book(client, cid, oid, start)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["revision"] == 1
    assert item["status"] == "scheduled"
    assert _book(client, cid, oid, start).json()["appointment_id"] == item["appointment_id"]
    assert _book(client, cid, oid, start + timedelta(minutes=15)).status_code == 409
    assert _book(client, cid, oid, start + timedelta(minutes=15),
                 key="f7-agenda-0002").status_code == 409
    assert _book(client, cid, oid, start + timedelta(hours=1),
                 key="f7-agenda-0003").status_code == 201

    listing = client.get("/v1/followups/agenda", params=_window(start))
    assert listing.status_code == 200, listing.text
    assert len(listing.json()["items"]) == 2
    slots = client.get("/v1/followups/agenda/slots", params={
        **_window(start, 2), "duration_minutes": 30, "step_minutes": 30,
    })
    assert slots.status_code == 200, slots.text
    assert all(not s["available"] for s in slots.json()["items"])
    assert client.get("/v1/followups/agenda/slots", params={
        **_window(start, 200),
    }).status_code == 409

    engine = client.app.state.agenda_engine
    with engine._sessions() as db:
        row = db.get(AgendaAppointmentORM, item["appointment_id"])
        assert "Encontro reservado" not in row.title_ciphertext

    assert client.post("/v1/followups/agenda", json={
        "contact_id": cid, "opportunity_id": oid, "title": "Bloqueado",
        "starts_at": start.isoformat(), "duration_minutes": 30,
        "idempotency_key": "f7-agenda-0004",
    }, headers={"Origin": "https://attacker.example"}).status_code == 403


def test_reschedule_cancel_complete_and_cross_unit(client):
    cid, oid, _ = _setup(client)
    start = datetime.now(UTC) + timedelta(days=3)
    item = _book(client, cid, oid, start).json()
    aid = item["appointment_id"]
    changed = client.post(f"/v1/followups/agenda/{aid}/reschedule", json={
        "expected_revision": 1,
        "starts_at": (start + timedelta(hours=3)).isoformat(),
        "duration_minutes": 30,
    })
    assert changed.status_code == 200, changed.text
    assert changed.json()["revision"] == 2
    assert client.post(f"/v1/followups/agenda/{aid}/cancel", json={
        "expected_revision": 1,
    }).status_code == 409
    events = client.get(f"/v1/followups/agenda/{aid}/events")
    assert [x["action"] for x in events.json()["items"]] == [
        "scheduled", "reschedule",
    ]

    assert client.post("/v1/units", json={
        "unit_id": "secondary", "display_name": "Outra unidade",
    }).status_code == 200
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "secondary",
    }).status_code == 200
    assert client.get(f"/v1/followups/agenda/{aid}/events").status_code == 404
    assert client.post(f"/v1/followups/agenda/{aid}/cancel", json={
        "expected_revision": 2,
    }).status_code == 404
    assert client.get("/v1/followups/agenda", params=_window(start)).json()["items"] == []

    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "unit-a",
    }).status_code == 200


def test_due_reminder_creates_exactly_one_encrypted_internal_task(client):
    cid, oid, _ = _setup(client)
    start = datetime.now(UTC) + timedelta(days=2)
    item = _book(client, cid, oid, start, title="Orçamento ultra sigiloso").json()
    engine = client.app.state.agenda_engine
    moment = start - timedelta(minutes=30)
    assert engine.reminders(now=moment)["reminded"] == 1
    assert engine.reminders(now=moment)["reminded"] == 0
    with engine._sessions() as db:
        rows = db.scalars(select(CRMActivityORM).where(
            CRMActivityORM.related_id == item["appointment_id"],
        )).all()
        assert len(rows) == 1
        assert rows[0].kind == "task"
        assert "Orçamento ultra sigiloso" not in rows[0].details_ciphertext
    assert "Orçamento ultra sigiloso" in client.get(
        f"/v1/crm/opportunities/{oid}/activities",
    ).text
    events = client.get(
        f"/v1/followups/agenda/{item['appointment_id']}/events",
    ).json()["items"]
    assert [x["action"] for x in events].count("reminded") == 1

    # A revision after a reminder is a new human-authorized appointment time.
    change = client.post(
        f"/v1/followups/agenda/{item['appointment_id']}/reschedule",
        json={
            "expected_revision": 1,
            "starts_at": (start + timedelta(days=1)).isoformat(),
            "duration_minutes": 60,
        },
    )
    assert change.status_code == 200, change.text
    assert engine.reminders(now=start + timedelta(hours=23))["reminded"] == 1
    assert engine.reminders(now=start + timedelta(hours=23))["reminded"] == 0


def test_cancelled_and_expired_meetings_never_project_tasks(client):
    cid, oid, _ = _setup(client)
    start = datetime.now(UTC) + timedelta(days=3)
    one = _book(client, cid, oid, start).json()
    cancel = client.post(
        f"/v1/followups/agenda/{one['appointment_id']}/cancel",
        json={"expected_revision": 1},
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    other = _book(client, cid, oid, start,
                  key="f7-agenda-0005").json()
    engine = client.app.state.agenda_engine
    outcome = engine.reminders(now=start + timedelta(minutes=1))
    assert outcome["reminded"] == 0
    assert outcome["expired"] == 1
    assert engine.reminders(now=start + timedelta(minutes=1))["expired"] == 0
    with engine._sessions() as db:
        assert not db.scalars(select(CRMActivityORM).where(
            CRMActivityORM.related_id == other["appointment_id"],
        )).all()
