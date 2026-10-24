"""F6 CRM: encrypted PII, deterministic pipeline and tenant authorization."""
from __future__ import annotations

from sqlalchemy import select
from test_identity_rbac import _bootstrap, _login

from fm_assistant.crm import CRMAuditORM, CRMContactORM, CRMOpportunityORM


def _contact(client, email="Vendas@Empresa.com.br"):
    return client.post("/v1/crm/contacts", json={
        "name": "Contato Comercial", "email": email,
    })


def _opportunity(client, contact_id, amount=12500):
    return client.post("/v1/crm/opportunities", json={
        "contact_id": contact_id, "title": "Contrato SaaS", "amount_cents": amount,
    })


def test_contacts_are_encrypted_scoped_and_deduplicated(client):
    _bootstrap(client)
    assert _contact(client).status_code == 401
    _login(client)
    created = _contact(client)
    assert created.status_code == 201, created.text
    contact = created.json()
    assert contact["name"] == "Contato Comercial"
    assert contact["email"] == "vendas@empresa.com.br"
    assert contact["revision"] == 1
    with client.app.state.crm._sessions() as db:
        row = db.get(CRMContactORM, contact["contact_id"])
        assert "vendas@empresa.com.br" not in row.email_ciphertext
        assert row.email_fingerprint != "vendas@empresa.com.br"
        audit = db.scalars(select(CRMAuditORM).where(
            CRMAuditORM.entity_id == contact["contact_id"],
        )).all()
        assert len(audit) == 1
        assert audit[0].action == "created"
        assert "vendas@empresa.com.br" not in str(audit[0].__dict__)
    dupe = _contact(client, "  vendas@empresa.com.br  ")
    assert dupe.status_code == 409
    assert dupe.json()["detail"] == "crm.contact_already_exists"
    assert len(client.get("/v1/crm/contacts").json()["items"]) == 1
    assert client.post("/v1/crm/contacts", json={
        "name": "Sem e-mail",
    }).status_code == 201
    assert len(client.get("/v1/crm/contacts").json()["items"]) == 2


def test_pipeline_transitions_are_cas_audited_and_terminal(client):
    _bootstrap(client)
    _login(client)
    cid = _contact(client).json()["contact_id"]
    created = _opportunity(client, cid)
    assert created.status_code == 201, created.text
    opportunity = created.json()
    assert opportunity["stage"] == "new"
    assert opportunity["revision"] == 1
    path = "/v1/crm/opportunities/" + opportunity["opportunity_id"] + "/transition"
    assert client.post(path, json={
        "expected_revision": 1, "stage": "won",
    }).status_code == 409
    for rev, stage in [(1, "qualified"), (2, "proposal"), (3, "won")]:
        moved = client.post(path, json={"expected_revision": rev, "stage": stage})
        assert moved.status_code == 200, moved.text
        assert moved.json()["stage"] == stage
        assert moved.json()["revision"] == rev + 1
        assert client.post(path, json={
            "expected_revision": rev, "stage": stage,
        }).status_code == 409
    assert client.post(path, json={
        "expected_revision": 4, "stage": "lost",
    }).status_code == 409
    assert client.get("/v1/crm/opportunities?stage=won").json()["items"][0][
        "opportunity_id"
    ] == opportunity["opportunity_id"]
    assert client.get("/v1/crm/opportunities?stage=bad").status_code == 422
    with client.app.state.crm._sessions() as db:
        assert db.get(CRMOpportunityORM, opportunity["opportunity_id"]).stage == "won"
        events = db.scalars(select(CRMAuditORM).where(
            CRMAuditORM.entity_id == opportunity["opportunity_id"],
        )).all()
        assert [event.action for event in events].count("transition") == 3
    assert _opportunity(client, cid, amount=True).status_code == 422
    assert _opportunity(client, cid, amount=-1).status_code == 422


def test_scope_enforced_on_reads_create_and_state_changes(client):
    _bootstrap(client)
    _bootstrap(client, tenant_id="tenant-b", unit_id="unit-b",
               email="owner-b@example.com")
    _login(client)
    cid = _contact(client).json()["contact_id"]
    opp = _opportunity(client, cid).json()["opportunity_id"]
    unit = client.post("/v1/units", json={
        "unit_id": "unit-next", "display_name": "Filial",
    })
    assert unit.status_code == 200
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "unit-next",
    }).status_code == 200
    assert client.get("/v1/crm/contacts").json()["items"] == []
    assert _opportunity(client, cid).status_code == 404
    assert client.post("/v1/crm/opportunities/" + opp + "/transition", json={
        "expected_revision": 1, "stage": "qualified",
    }).status_code == 404
    assert _contact(client).status_code == 201  # Same email allowed in another unit.
    client.post("/v1/auth/logout")
    _login(client, tenant_id="tenant-b", email="owner-b@example.com")
    assert client.get("/v1/crm/contacts").json()["items"] == []
    assert client.get("/v1/crm/opportunities").json()["items"] == []
    assert _opportunity(client, cid).status_code == 404
    assert client.post("/v1/crm/opportunities/" + opp + "/transition", json={
        "expected_revision": 1, "stage": "qualified",
    }).status_code == 404
    assert _contact(client).status_code == 201  # Same email allowed in another tenant.


def test_human_rbac_csrf_and_machine_denied(client):
    _bootstrap(client)
    _login(client)
    assert client.post("/v1/crm/contacts", json={
        "name": "External", "email": "external@example.org",
    }, headers={"Origin": "https://foreign.example"}).status_code == 403
    invite = client.post("/v1/users/invitations", json={
        "email": "reader@example.org", "role": "viewer", "unit_id": "unit-a",
    }).json()["invitation_token"]
    client.post("/v1/auth/logout")
    assert client.post("/v1/auth/accept-invitation", json={
        "invitation_token": invite, "display_name": "Reader",
        "password": "ViewerPassword!123",
    }).status_code == 200
    _login(client, email="reader@example.org", password="ViewerPassword!123")
    assert client.get("/v1/crm/contacts").status_code == 200
    assert _contact(client).status_code == 403
    assert client.post("/v1/crm/opportunities", json={
        "contact_id": "00000000-0000-4000-8000-000000000001",
        "title": "Denied", "amount_cents": 10,
    }).status_code == 403


def test_crm_workspace_is_session_only_and_exposes_no_inline_external_scripts(client):
    assert client.get("/app/crm").status_code == 401
    _bootstrap(client)
    _login(client)
    response = client.get("/app/crm")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "script-src 'sha256-" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "no-store" == response.headers["cache-control"]
    assert "Contatos" in response.text
    assert "opportunities" in response.text
    assert "/app/crm" in client.get("/app/knowledge").text
    assert "/app/crm" in client.get("/app/inbox").text
