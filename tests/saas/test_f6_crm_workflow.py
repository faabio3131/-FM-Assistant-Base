"""F6 operational CRM extension: real HTTP, SQLite, scoped secrets and lifecycle."""
from __future__ import annotations

from sqlalchemy import select
from test_identity_rbac import _bootstrap, _login

from fm_assistant.crm import CRMAuditORM
from fm_assistant.crm_workflow import (
    CRMActivityORM,
    CRMConversationLinkORM,
    CRMProposalORM,
    CRMQualificationORM,
    qualification_score,
)


def seed(client):
    _bootstrap(client)
    _login(client)
    contact = client.post("/v1/crm/contacts", json={
        "name": "Pessoa", "email": "cliente@example.org",
    })
    assert contact.status_code == 201, contact.text
    cid = contact.json()["contact_id"]
    opportunity = client.post("/v1/crm/opportunities", json={
        "contact_id": cid, "title": "Implantação SaaS", "amount_cents": 39900,
    })
    assert opportunity.status_code == 201, opportunity.text
    conversation = client.post("/v1/conversations", json={"channel": "api"})
    assert conversation.status_code == 200, conversation.text
    return cid, opportunity.json()["opportunity_id"], conversation.json()["conversation_id"]


def test_link_conversation_checks_source_scope_contact_match_and_revision(client):
    contact, opportunity, conversation = seed(client)
    uri = f"/v1/crm/conversations/{conversation}/link"
    assert client.get(uri).status_code == 404
    linked = client.put(uri, json={
        "contact_id": contact, "opportunity_id": opportunity, "expected_revision": 0,
    })
    assert linked.status_code == 200, linked.text
    assert linked.json()["revision"] == 1
    assert client.get(uri).json()["opportunity_id"] == opportunity
    assert client.get(f"/v1/crm/opportunities/{opportunity}/conversations").json()[
        "items"
    ][0]["conversation_id"] == conversation
    assert client.put(uri, json={
        "contact_id": contact, "opportunity_id": opportunity, "expected_revision": 0,
    }).status_code == 409
    assert client.put(uri, json={
        "contact_id": contact, "opportunity_id": None, "expected_revision": 1,
    }).json()["revision"] == 2
    assert client.get(f"/v1/crm/opportunities/{opportunity}/conversations").json()[
        "items"
    ] == []
    assert client.put(uri, json={
        "contact_id": contact, "opportunity_id": opportunity,
        "expected_revision": True,
    }).status_code == 422
    with client.app.state.crm._sessions() as db:
        assert db.get(CRMConversationLinkORM, conversation).revision == 2


def test_qualification_is_explainable_separate_from_stage_and_cas(client):
    _contact, opp, _conversation = seed(client)
    path = f"/v1/crm/opportunities/{opp}/qualification"
    base = {
        "need_confirmed": True, "budget_confirmed": True,
        "decision_maker_confirmed": False, "timeline_days": 20,
    }
    assert qualification_score(True, True, False, 20) == 70
    assert qualification_score(True, True, True, 91) == 85
    assert client.get(path).status_code == 404
    response = client.put(path, json={**base, "expected_revision": 0})
    assert response.status_code == 200, response.text
    assert response.json()["score"] == 70
    assert response.json()["revision"] == 1
    assert client.put(path, json={**base, "expected_revision": 0}).status_code == 409
    assert client.put(path, json={**base, "timeline_days": True,
                                  "expected_revision": 1}).status_code == 422
    revised = client.put(path, json={**base, "decision_maker_confirmed": True,
                                     "expected_revision": 1})
    assert revised.status_code == 200
    assert revised.json()["score"] == 100
    assert revised.json()["revision"] == 2
    pipeline = client.get("/v1/crm/opportunities").json()["items"][0]
    assert pipeline["stage"] == "new"  # Scoring never silently promotes pipeline.
    with client.app.state.crm._sessions() as db:
        assert db.get(CRMQualificationORM, opp).score == 100


def test_proposal_snapshot_private_terms_and_governed_approval(client):
    _contact, opp, _conversation = seed(client)
    root = f"/v1/crm/opportunities/{opp}"
    proposal = root + "/proposals"
    assert client.post(proposal, json={
        "title": "Orçamento", "terms": "Condições do cliente X",
    }).status_code == 409
    assert client.post(root + "/transition", json={
        "expected_revision": 1, "stage": "qualified",
    }).status_code == 200
    assert client.post(root + "/transition", json={
        "expected_revision": 2, "stage": "proposal",
    }).status_code == 200
    created = client.post(proposal, json={
        "title": "Condições FM", "terms": "Pagamento somente após aceite formal.",
    })
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["status"] == "draft"
    assert item["revision"] == 1
    assert item["amount_cents"] == 39900
    assert "Pagamento somente" in item["terms"]
    with client.app.state.crm._sessions() as db:
        row = db.get(CRMProposalORM, item["proposal_id"])
        assert "Pagamento somente" not in row.terms_ciphertext
        assert row.amount_cents == 39900
    assert len(client.get(proposal).json()["items"]) == 1
    update = proposal + "/" + item["proposal_id"] + "/status"
    assert client.post(update, json={
        "expected_revision": 1, "status": "ready",
    }).json()["status"] == "ready"
    assert client.post(update, json={
        "expected_revision": 1, "status": "withdrawn",
    }).status_code == 409
    assert client.post(update, json={
        "expected_revision": 2, "status": "withdrawn",
    }).status_code == 409
    assert client.get("/v1/crm/opportunities").json()["items"][0]["stage"] == "proposal"
    assert client.post(root + "/transition", json={
        "expected_revision": 3, "stage": "won",
    }).status_code == 200
    assert client.post(proposal, json={
        "title": "Novo após venda", "terms": "Não permitido",
    }).status_code == 409


def test_activities_are_private_encrypted_audited_and_bounded(client):
    _contact, opportunity, _conversation = seed(client)
    url = f"/v1/crm/opportunities/{opportunity}/activities"
    sensitive = "Cliente solicitou orçamento particular por telefone"
    stored = client.post(url, json={"kind": "call", "details": sensitive})
    assert stored.status_code == 201, stored.text
    with client.app.state.crm._sessions() as db:
        notes = db.scalars(select(CRMActivityORM).where(
            CRMActivityORM.opportunity_id == opportunity,
        )).all()
        assert len(notes) == 1
        assert sensitive not in notes[0].details_ciphertext
        assert db.scalar(select(CRMAuditORM).where(
            CRMAuditORM.entity_id == opportunity,
            CRMAuditORM.action == "activity",
        )) is not None
    assert client.get(url).json()["items"][0]["details"] == sensitive
    assert client.post(url, json={"kind": "unknown",
                                  "details": sensitive}).status_code == 422
    assert client.get(url + "?page=201").status_code == 422


def test_foreign_tenant_unit_and_wrong_contact_cannot_link_or_read(client):
    contact, opportunity, conversation = seed(client)
    foreign_contact = client.post("/v1/crm/contacts", json={
        "name": "Outro contato",
    }).json()["contact_id"]
    path = f"/v1/crm/conversations/{conversation}/link"
    wrong = client.put(path, json={
        "contact_id": foreign_contact, "opportunity_id": opportunity,
        "expected_revision": 0,
    })
    assert wrong.status_code == 409
    assert client.put(path, json={
        "contact_id": contact, "opportunity_id": opportunity,
        "expected_revision": 0,
    }).status_code == 200
    assert client.post("/v1/units", json={
        "unit_id": "unit-other", "display_name": "Outra filial",
    }).status_code == 200
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "unit-other",
    }).status_code == 200
    assert client.get(path).status_code == 404
    assert client.get(f"/v1/crm/opportunities/{opportunity}/activities").status_code == 404
    assert client.get(
        f"/v1/crm/opportunities/{opportunity}/proposals",
    ).status_code == 404
    assert client.put(path, json={
        "contact_id": contact, "opportunity_id": opportunity,
        "expected_revision": 1,
    }).status_code == 404
    client.post("/v1/auth/logout")
    _bootstrap(client, tenant_id="other-tenant", unit_id="unit-a",
               email="another@example.org")
    _login(client, tenant_id="other-tenant", email="another@example.org")
    assert client.get(path).status_code == 404
    assert client.get(f"/v1/crm/opportunities/{opportunity}/qualification").status_code == 404


def test_mutations_require_manage_role_and_same_origin(client):
    contact, opp, convo = seed(client)
    mutation = f"/v1/crm/conversations/{convo}/link"
    assert client.put(mutation, headers={"Origin": "https://other.test"}, json={
        "contact_id": contact, "expected_revision": 0,
    }).status_code == 403
    invite = client.post("/v1/users/invitations", json={
        "email": "viewer-workflow@example.org", "role": "viewer", "unit_id": "unit-a",
    }).json()["invitation_token"]
    client.post("/v1/auth/logout")
    assert client.post("/v1/auth/accept-invitation", json={
        "invitation_token": invite, "display_name": "Viewer",
        "password": "ViewerPassword!123",
    }).status_code == 200
    _login(client, email="viewer-workflow@example.org", password="ViewerPassword!123")
    assert client.put(mutation, json={
        "contact_id": contact, "expected_revision": 0,
    }).status_code == 403
    assert client.get(f"/v1/crm/opportunities/{opp}/qualification").status_code == 404
    assert client.get(f"/v1/crm/opportunities/{opp}/activities").status_code == 403
    assert client.get(f"/v1/crm/opportunities/{opp}/proposals").status_code == 403
    assert client.post(f"/v1/crm/opportunities/{opp}/activities", json={
        "kind": "note", "details": "Denied",
    }).status_code == 403
