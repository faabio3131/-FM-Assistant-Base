"""F7 contact suppression: adversarial HTTP state and UTC/local-clock checks."""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from test_identity_rbac import _bootstrap, _login

from fm_assistant.crm import CRMAuditORM
from fm_assistant.followups import FollowupPreferenceORM, quiet_now


def create_contact(client):
    r = client.post("/v1/crm/contacts", json={"name": "Lead para acompanhamento"})
    assert r.status_code == 201, r.text
    return r.json()["contact_id"]


def policy(**changes):
    return {
        "channel": "whatsapp", "expected_revision": 0,
        "opted_out": False, "timezone": "America/Sao_Paulo",
        "quiet_start": "22:00", "quiet_end": "08:00", **changes,
    }


def test_f7_unconfigured_denies_dispatch_and_cas_prevents_stale_writes(client):
    _bootstrap(client)
    assert client.get("/v1/followups/contacts/invalid/preferences").status_code == 401
    _login(client)
    cid = create_contact(client)
    path = f"/v1/followups/contacts/{cid}/preferences"
    before = client.get(path)
    assert before.status_code == 200, before.text
    assert before.json()["configured"] is False
    assert before.json()["can_dispatch"] is False
    assert before.json()["reason"] == "unconfigured"
    first = client.put(path, json=policy())
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1
    assert first.json()["configured"] is True
    assert client.put(path, json=policy()).status_code == 409
    second = client.put(path, json=policy(
        expected_revision=1, quiet_start="21:00",
    ))
    assert second.status_code == 200, second.text
    assert second.json()["revision"] == 2
    assert second.json()["quiet_start"] == "21:00"
    assert client.get(path).json()["revision"] == 2
    with client.app.state.crm._sessions() as db:
        rows = db.scalars(select(FollowupPreferenceORM).where(
            FollowupPreferenceORM.contact_id == cid,
        )).all()
        assert len(rows) == 1 and rows[0].revision == 2
        audits = db.scalars(select(CRMAuditORM).where(
            CRMAuditORM.entity_kind == "followup",
            CRMAuditORM.entity_id == cid,
        )).all()
        assert len(audits) == 2
        assert all(a.action == "policy_updated" for a in audits)


def test_opt_out_is_sticky_without_consent_proof(client):
    _bootstrap(client)
    _login(client)
    cid = create_contact(client)
    path = f"/v1/followups/contacts/{cid}/preferences"
    stored = client.put(path, json=policy(opted_out=True))
    assert stored.status_code == 200, stored.text
    assert stored.json()["can_dispatch"] is False
    assert stored.json()["reason"] == "opted_out"
    illegal = client.put(path, json=policy(
        expected_revision=1, opted_out=False,
    ))
    assert illegal.status_code == 409
    assert illegal.json()["detail"] == "followup.consent_evidence_required"
    unchanged = client.get(path)
    assert unchanged.json()["revision"] == 1
    assert unchanged.json()["opted_out"] is True
    # WhatsApp opt-out must not be reused as implied consent to email.
    other_channel = client.get(path + "?channel=email").json()
    assert other_channel["configured"] is False
    assert other_channel["can_dispatch"] is False


def test_invalid_tz_clock_and_extra_payload_fail_closed(client):
    _bootstrap(client)
    _login(client)
    cid = create_contact(client)
    path = f"/v1/followups/contacts/{cid}/preferences"
    for values in (
        {"timezone": "Invalid/Nowhere"},
        {"quiet_start": "24:00"},
        {"quiet_start": "08:00"},
        {"opted_out": 0},
        {"expected_revision": True},
        {"channel": "sms"},
        {"unknown": "must fail"},
    ):
        response = client.put(path, json=policy(**values))
        assert response.status_code in {409, 422}, (values, response.text)
    assert client.get(path).json()["configured"] is False
    assert client.get(path + "?channel=unknown").status_code == 422
    assert client.put(path, json=policy(), headers={
        "Origin": "https://attacker.invalid",
    }).status_code == 403
    assert client.get(path).json()["configured"] is False


def test_contact_tenant_and_unit_isolation(client):
    _bootstrap(client)
    _bootstrap(client, tenant_id="tenant-b", unit_id="unit-b",
               email="owner-b@example.com")
    _login(client)
    cid = create_contact(client)
    path = f"/v1/followups/contacts/{cid}/preferences"
    assert client.put(path, json=policy(opted_out=True)).status_code == 200
    assert client.post("/v1/units", json={
        "unit_id": "unit-other", "display_name": "Unidade B",
    }).status_code == 200
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "unit-other",
    }).status_code == 200
    assert client.get(path).status_code == 404
    assert client.put(path, json=policy()).status_code == 404
    client.post("/v1/auth/logout")
    _login(client, tenant_id="tenant-b", email="owner-b@example.com")
    assert client.get(path).status_code == 404
    assert client.put(path, json=policy()).status_code == 404


def test_timezone_quiet_hours_include_overnight_and_dst_utc_mapping():
    local = ZoneInfo("America/Sao_Paulo")
    assert str(local) == "America/Sao_Paulo"
    assert quiet_now(datetime(2026, 10, 24, 1, tzinfo=UTC), str(local),
                     22 * 60, 8 * 60) is True  # 22:00 in Brazil.
    assert quiet_now(datetime(2026, 10, 24, 11, tzinfo=UTC), str(local),
                     22 * 60, 8 * 60) is False  # 08:00 in Brazil.
    assert quiet_now(datetime(2026, 10, 24, 13, tzinfo=UTC), str(local),
                     10 * 60, 12 * 60) is True
    assert quiet_now(datetime(2026, 10, 24, 15, tzinfo=UTC), str(local),
                     10 * 60, 12 * 60) is False
    # DST is evaluated from a real UTC instant, not a guessed local offset.
    assert quiet_now(datetime(2026, 11, 1, 5, 30, tzinfo=UTC),
                     "America/New_York", 60, 120) is True
    assert quiet_now(datetime(2026, 11, 1, 6, 30, tzinfo=UTC),
                     "America/New_York", 60, 120) is True
