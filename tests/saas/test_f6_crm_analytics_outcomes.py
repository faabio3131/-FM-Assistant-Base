"""F6 CRM funnel and outcome certification on real session-scoped HTTP/DB."""
from __future__ import annotations

from sqlalchemy import select
from test_identity_rbac import _bootstrap, _login

from fm_assistant.crm import CRMAuditORM, CRMOpportunityORM
from fm_assistant.crm_workflow import CRMActivityORM


def contact(client, name="Lead"):
    response = client.post("/v1/crm/contacts", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["contact_id"]


def opportunity(client, contact_id, amount=20000):
    response = client.post("/v1/crm/opportunities", json={
        "contact_id": contact_id, "title": "Venda recorrente",
        "amount_cents": amount,
    })
    assert response.status_code == 201, response.text
    return response.json()


def transition(client, item, stage, reason=None):
    return client.post(f"/v1/crm/opportunities/{item['opportunity_id']}/transition", json={
        "expected_revision": item["revision"], "stage": stage,
        "outcome_reason": reason,
    })


def test_funnel_counts_all_records_and_distinguishes_pipeline_from_revenue(client):
    _bootstrap(client)
    _login(client)
    empty = client.get("/v1/crm/analytics")
    assert empty.status_code == 200
    assert empty.json()["win_rate_basis_points"] is None
    assert empty.json()["opportunities_total"] == 0
    cid = contact(client)
    entries = [opportunity(client, cid, amount) for amount in (10000, 30000, 50000)]
    assert transition(client, entries[0], "lost", "Sem prazo de contratação").status_code == 200
    qualified = transition(client, entries[1], "qualified")
    assert qualified.status_code == 200
    proposed = transition(client, qualified.json(), "proposal")
    assert proposed.status_code == 200
    won = transition(client, proposed.json(), "won", "Aprovado na reunião")
    assert won.status_code == 200
    result = client.get("/v1/crm/analytics")
    assert result.status_code == 200
    snapshot = result.json()
    assert snapshot["currency"] == "BRL"
    assert snapshot["revenue_recognized"] is False
    assert snapshot["contacts_total"] == 1
    assert snapshot["opportunities_total"] == 3
    assert snapshot["open_opportunities"] == 1
    assert snapshot["open_pipeline_cents"] == 50000
    assert snapshot["won_opportunities"] == 1
    assert snapshot["won_opportunity_value_cents"] == 30000
    assert snapshot["lost_opportunities"] == 1
    assert snapshot["closed_opportunities"] == 2
    assert snapshot["win_rate_basis_points"] == 5000
    assert snapshot["stages"]["lost"] == {"count": 1, "amount_cents": 10000}
    assert snapshot["stages"]["won"] == {"count": 1, "amount_cents": 30000}
    assert snapshot["stages"]["new"] == {"count": 1, "amount_cents": 50000}
    assert "cliente" not in str(snapshot).lower()


def test_terminal_reason_encrypted_atomic_and_does_not_leak_in_pipeline(client):
    _bootstrap(client)
    _login(client)
    item = opportunity(client, contact(client))
    reason = "Cliente particular desistiu por prazo confidencial"
    wrong = transition(client, item, "qualified", reason)
    assert wrong.status_code == 409
    assert wrong.json()["detail"] == "crm.outcome_reason_invalid"
    lost = transition(client, item, "lost", reason)
    assert lost.status_code == 200, lost.text
    again = transition(client, item, "lost", "segunda tentativa")
    assert again.status_code == 409
    with client.app.state.crm._sessions() as db:
        row = db.get(CRMOpportunityORM, item["opportunity_id"])
        assert row.stage == "lost" and row.revision == 2
        activities = db.scalars(select(CRMActivityORM).where(
            CRMActivityORM.opportunity_id == item["opportunity_id"],
        )).all()
        assert len(activities) == 1
        assert activities[0].kind == "outcome_lost"
        assert reason not in activities[0].details_ciphertext
        audit = db.scalars(select(CRMAuditORM).where(
            CRMAuditORM.entity_id == item["opportunity_id"],
            CRMAuditORM.action == "transition",
        )).all()
        assert len(audit) == 1
    history = client.get(
        f"/v1/crm/opportunities/{item['opportunity_id']}/activities",
    )
    assert history.status_code == 200
    assert history.json()["items"][0]["details"] == reason
    analytics = client.get("/v1/crm/analytics").json()
    assert reason not in str(analytics)
    assert reason not in client.get("/v1/crm/opportunities").text
    assert transition(client, item, "lost", "").status_code == 422
    assert transition(client, item, "lost", "x" * 501).status_code == 422


def test_funnel_reads_are_not_paginated_and_scoped_by_tenant_and_unit(client):
    _bootstrap(client)
    _bootstrap(client, tenant_id="tenant-b", unit_id="unit-b",
               email="owner-b@example.com")
    _login(client)
    cid = contact(client)
    for i in range(55):
        opportunity(client, cid, i + 1)
    result = client.get("/v1/crm/analytics").json()
    assert result["opportunities_total"] == 55
    assert result["open_pipeline_cents"] == sum(range(1, 56))
    assert len(client.get("/v1/crm/opportunities").json()["items"]) == 50
    created = client.post("/v1/units", json={
        "unit_id": "unit-other", "display_name": "Outra unidade",
    })
    assert created.status_code == 200, created.text
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "unit-other",
    }).status_code == 200
    other = client.get("/v1/crm/analytics").json()
    assert other["contacts_total"] == 0
    assert other["opportunities_total"] == 0
    assert other["open_pipeline_cents"] == 0
    client.post("/v1/auth/logout")
    _login(client, tenant_id="tenant-b", email="owner-b@example.com")
    foreign = client.get("/v1/crm/analytics").json()
    assert foreign["opportunities_total"] == 0
    assert foreign["contacts_total"] == 0


def test_funnel_read_requires_session_and_mutations_require_same_origin(client):
    _bootstrap(client)
    assert client.get("/v1/crm/analytics").status_code == 401
    _login(client)
    item = opportunity(client, contact(client))
    path = f"/v1/crm/opportunities/{item['opportunity_id']}/transition"
    denied = client.post(path, json={
        "expected_revision": 1, "stage": "lost", "outcome_reason": "Segredo",
    }, headers={"Origin": "https://attacker.example"})
    assert denied.status_code in {403, 409}
    assert client.get("/v1/crm/analytics").json()["stages"]["new"]["count"] == 1
