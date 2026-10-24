from __future__ import annotations

from sqlalchemy import create_engine, text

OWNER_PASSWORD = "OwnerPassword!123"
VIEWER_PASSWORD = "ViewerPassword!123"
MANAGER_PASSWORD = "ManagerPassword!123"


def _bootstrap(
    client,
    *,
    tenant_id: str = "tenant-a",
    unit_id: str = "unit-a",
    email: str = "owner-a@example.com",
):
    response = client.post(
        "/v1/bootstrap/tenant-owner",
        headers={"X-Admin-Key": "admin-test-key"},
        json={
            "tenant_id": tenant_id,
            "tenant_name": f"Empresa {tenant_id}",
            "unit_id": unit_id,
            "unit_name": f"Unidade {unit_id}",
            "owner_email": email,
            "owner_name": "Owner",
            "password": OWNER_PASSWORD,
            "plan_code": "trial",
            "trial_days": 14,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _login(
    client,
    *,
    tenant_id: str = "tenant-a",
    email: str = "owner-a@example.com",
    password: str = OWNER_PASSWORD,
    unit_id: str | None = None,
):
    payload = {
        "tenant_id": tenant_id,
        "email": email,
        "password": password,
    }
    if unit_id is not None:
        payload["unit_id"] = unit_id
    response = client.post("/v1/auth/login", json=payload)
    assert response.status_code == 200, response.text
    return response


def test_owner_session_unit_switch_and_logout(client):
    _bootstrap(client)
    login = _login(client)

    set_cookie = login.headers["set-cookie"].casefold()
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie

    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "owner"
    assert me.json()["unit_id"] == "unit-a"
    assert "unit.manage" in me.json()["permissions"]

    created = client.post(
        "/v1/units",
        json={"unit_id": "unit-b", "display_name": "Unidade B"},
    )
    assert created.status_code == 200, created.text

    switched = client.post("/v1/auth/switch-unit", json={"unit_id": "unit-b"})
    assert switched.status_code == 200
    assert switched.json()["unit_id"] == "unit-b"

    logged_out = client.post("/v1/auth/logout")
    assert logged_out.status_code == 204

    denied = client.get("/v1/auth/me")
    assert denied.status_code == 401


def test_viewer_is_deny_by_default_for_management(client):
    _bootstrap(client)
    _login(client)

    invited = client.post(
        "/v1/users/invitations",
        json={
            "email": "viewer@example.com",
            "role": "viewer",
            "unit_id": "unit-a",
            "expires_hours": 72,
        },
    )
    assert invited.status_code == 200, invited.text
    token = invited.json()["invitation_token"]

    client.post("/v1/auth/logout")
    accepted = client.post(
        "/v1/auth/accept-invitation",
        json={
            "invitation_token": token,
            "display_name": "Viewer",
            "password": VIEWER_PASSWORD,
        },
    )
    assert accepted.status_code == 200, accepted.text

    _login(
        client,
        email="viewer@example.com",
        password=VIEWER_PASSWORD,
    )

    units = client.get("/v1/units")
    assert units.status_code == 200
    assert units.json() == [{"unit_id": "unit-a", "display_name": "Unidade unit-a"}]

    create_unit = client.post(
        "/v1/units",
        json={"unit_id": "forbidden", "display_name": "Forbidden"},
    )
    assert create_unit.status_code == 403

    invite = client.post(
        "/v1/users/invitations",
        json={
            "email": "other@example.com",
            "role": "viewer",
            "unit_id": "unit-a",
        },
    )
    assert invite.status_code == 403


def test_manager_cannot_escalate_role_to_admin(client):
    _bootstrap(client)
    _login(client)

    invited = client.post(
        "/v1/users/invitations",
        json={
            "email": "manager@example.com",
            "role": "manager",
            "unit_id": "unit-a",
        },
    )
    assert invited.status_code == 200
    token = invited.json()["invitation_token"]
    client.post("/v1/auth/logout")

    accepted = client.post(
        "/v1/auth/accept-invitation",
        json={
            "invitation_token": token,
            "display_name": "Manager",
            "password": MANAGER_PASSWORD,
        },
    )
    assert accepted.status_code == 200

    _login(
        client,
        email="manager@example.com",
        password=MANAGER_PASSWORD,
    )
    escalation = client.post(
        "/v1/users/invitations",
        json={
            "email": "admin@example.com",
            "role": "admin",
            "unit_id": "unit-a",
        },
    )
    assert escalation.status_code == 403
    assert escalation.json()["detail"] == "role_assignment_forbidden"


def test_api_credential_is_machine_principal_not_human_session(client):
    _bootstrap(client)
    _login(client)

    created = client.post("/v1/api-credentials")
    assert created.status_code == 200, created.text
    api_key = created.json()["api_key"]

    client.post("/v1/auth/logout")

    persona = client.put(
        "/v1/persona",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "public_name": "Comercial IA",
            "language": "pt-BR",
            "tone": "consultivo",
            "instructions": "",
            "enabled": True,
        },
    )
    assert persona.status_code == 200, persona.text

    human_only = client.post(
        "/v1/units",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"unit_id": "x", "display_name": "X"},
    )
    assert human_only.status_code == 401


def test_session_cannot_cross_tenant_or_unit_boundary(client):
    _bootstrap(
        client,
        tenant_id="tenant-a",
        unit_id="unit-a",
        email="owner-a@example.com",
    )
    _bootstrap(
        client,
        tenant_id="tenant-b",
        unit_id="unit-b",
        email="owner-b@example.com",
    )
    _login(client, tenant_id="tenant-a", email="owner-a@example.com")

    switch = client.post("/v1/auth/switch-unit", json={"unit_id": "unit-b"})
    assert switch.status_code == 403

    invite_foreign_unit = client.post(
        "/v1/users/invitations",
        json={
            "email": "user@example.com",
            "role": "viewer",
            "unit_id": "unit-b",
        },
    )
    assert invite_foreign_unit.status_code == 404


def test_invalid_password_does_not_create_session(client):
    _bootstrap(client)

    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_id": "tenant-a",
            "email": "owner-a@example.com",
            "password": "wrong-password",
        },
    )
    assert response.status_code == 401
    assert "fm_assistant_session" not in client.cookies


def test_session_token_is_never_stored_in_plaintext(client):
    _bootstrap(client)
    _login(client)

    raw_token = client.cookies.get("fm_assistant_session")
    assert raw_token is not None

    engine = create_engine(client.app.state.settings.database_url)
    with engine.connect() as connection:
        stored_hash = connection.execute(
            text("SELECT token_hash FROM assistant_sessions")
        ).scalar_one()

    assert stored_hash != raw_token
    assert len(stored_hash) == 64
    assert raw_token not in stored_hash


def test_password_recovery_is_one_time_and_revokes_existing_sessions(client):
    _bootstrap(client)
    _login(client)

    recovery = client.post(
        "/v1/auth/recovery/request",
        json={"tenant_id": "tenant-a", "email": "owner-a@example.com"},
    )
    assert recovery.status_code == 202
    token = recovery.json()["recovery_token"]
    assert token.startswith("fmr_")

    completed = client.post(
        "/v1/auth/recovery/complete",
        json={
            "recovery_token": token,
            "new_password": "NewOwnerPassword!456",
        },
    )
    assert completed.status_code == 204

    assert client.get("/v1/auth/me").status_code == 401

    reused = client.post(
        "/v1/auth/recovery/complete",
        json={
            "recovery_token": token,
            "new_password": "AnotherPassword!789",
        },
    )
    assert reused.status_code == 400

    old_login = client.post(
        "/v1/auth/login",
        json={
            "tenant_id": "tenant-a",
            "email": "owner-a@example.com",
            "password": OWNER_PASSWORD,
        },
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/v1/auth/login",
        json={
            "tenant_id": "tenant-a",
            "email": "owner-a@example.com",
            "password": "NewOwnerPassword!456",
        },
    )
    assert new_login.status_code == 200


def test_recovery_request_does_not_reveal_unknown_account(client):
    response = client.post(
        "/v1/auth/recovery/request",
        json={"tenant_id": "missing", "email": "nobody@example.com"},
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": True, "recovery_token": None}
