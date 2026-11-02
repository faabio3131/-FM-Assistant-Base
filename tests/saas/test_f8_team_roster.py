"""F8 scoped team roster read model; no identity or secret duplication."""
from __future__ import annotations

from test_f8_commercial_settings import _invite_role
from test_identity_rbac import MANAGER_PASSWORD, _bootstrap, _login


def _invite_and_accept(client, *, email, name, unit_id="unit-a", role="viewer"):
    invitation = client.post("/v1/users/invitations", json={
        "email": email, "role": role, "unit_id": unit_id,
    })
    assert invitation.status_code == 200, invitation.text
    accepted = client.post("/v1/auth/accept-invitation", json={
        "invitation_token": invitation.json()["invitation_token"],
        "display_name": name, "password": "AcceptedPassword!123",
    })
    assert accepted.status_code == 200, accepted.text
    return accepted.json()["user_id"]


def test_team_listing_requires_permission_and_never_exposes_credentials(client):
    assert client.get("/v1/users").status_code == 401
    _bootstrap(client)
    _login(client)
    member_id = _invite_and_accept(
        client, email="staff-f8@example.com", name="Colaborador F8",
    )
    roster = client.get("/v1/users")
    assert roster.status_code == 200, roster.text
    assert roster.headers.get("content-type", "").startswith("application/json")
    assert roster.json()["next_page"] is None
    assert member_id in {item["user_id"] for item in roster.json()["items"]}
    assert {item["display_name"] for item in roster.json()["items"]} == {
        "Owner", "Colaborador F8",
    }
    assert all(item.keys() == {"user_id", "display_name", "role"}
               for item in roster.json()["items"])
    assert "staff-f8@example.com" not in roster.text
    assert "AcceptedPassword" not in roster.text
    assert "invitation_token" not in roster.text
    assert client.get("/v1/users?page=-1").status_code == 422
    assert client.get("/v1/users?page=201").status_code == 422


def test_team_roster_isolated_by_signed_unit_and_tenant(client):
    _bootstrap(client)
    _login(client)
    a = _invite_and_accept(
        client, email="unit-one-f8@example.com", name="Equipe Unidade A",
    )
    assert client.post("/v1/units", json={
        "unit_id": "unit-b", "display_name": "Unidade B",
    }).status_code == 200
    b = _invite_and_accept(
        client, email="unit-two-f8@example.com",
        name="Equipe Unidade B", unit_id="unit-b",
    )
    first = client.get("/v1/users", headers={
        "X-Tenant-ID": "foreign", "X-Unit-ID": "unit-b",
    })
    assert first.status_code == 200
    first_ids = {item["user_id"] for item in first.json()["items"]}
    assert a in first_ids and b not in first_ids

    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "unit-b",
    }).status_code == 200
    second = client.get("/v1/users")
    assert second.status_code == 200
    second_ids = {item["user_id"] for item in second.json()["items"]}
    assert b in second_ids and a not in second_ids
    assert "Equipe Unidade A" not in second.text

    _bootstrap(client, tenant_id="foreign", unit_id="unit-a",
               email="foreign-team-owner@example.com")
    _login(client, tenant_id="foreign", email="foreign-team-owner@example.com")
    third = client.get("/v1/users")
    assert third.status_code == 200
    assert not (first_ids | second_ids) & {
        item["user_id"] for item in third.json()["items"]
    }


def test_non_user_read_role_cannot_access_roster(client):
    _bootstrap(client)
    _login(client)
    _invite_and_accept(
        client, email="limited-team-f8@example.com", name="Agente Limitado",
        role="support_agent",
    )
    assert client.post("/v1/auth/logout").status_code == 204
    _login(client, email="limited-team-f8@example.com",
           password="AcceptedPassword!123")
    assert client.get("/v1/users").status_code == 403
    settings = client.get("/app/settings")
    assert settings.status_code == 200
    assert 'id="team-members"' not in settings.text


def test_team_settings_ui_renders_non_secret_roster_controls(client):
    _bootstrap(client)
    _login(client)
    page = client.get("/app/settings")
    assert page.status_code == 200
    assert 'id="team-members"' in page.text
    assert 'id="team-reload"' in page.text
    assert 'id="team-next"' in page.text
    assert 'id="team-previous"' in page.text
    assert '"/v1/users?page="+page' in page.text
    assert 'member.display_name' in page.text
    assert "member.email" not in page.text
    assert "innerHTML" not in page.text


def test_manager_invitation_choices_respect_role_assignment_policy(client):
    _bootstrap(client)
    _login(client)
    owner = client.get("/app/settings")
    assert '<option value="manager">Gerente</option>' in owner.text
    _invite_role(
        client, "roster-manager@example.com", "manager", MANAGER_PASSWORD,
    )
    manager = client.get("/app/settings")
    assert manager.status_code == 200
    assert 'id="team-form"' in manager.text
    assert '<option value="manager">Gerente</option>' not in manager.text
    assert '<option value="sales_agent">Comercial</option>' in manager.text
    assert '<option value="viewer">Leitura</option>' in manager.text
