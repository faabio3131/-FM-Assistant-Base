"""F8 settings page uses existing RBAC authority and CSP-protected controls."""
from __future__ import annotations

import base64
import hashlib
import re

from test_identity_rbac import (
    MANAGER_PASSWORD,
    VIEWER_PASSWORD,
    _bootstrap,
    _login,
)


def _assert_hashed_page(response):
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    script = re.search(r"<script>(.*?)</script>", response.text, re.DOTALL)
    assert script is not None
    digest = base64.b64encode(hashlib.sha256(
        script.group(1).encode(),
    ).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in (
        response.headers["content-security-policy"]
    )
    assert "innerHTML" not in response.text
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text


def _invite_role(client, email, role, password):
    invite = client.post("/v1/users/invitations", json={
        "email": email, "role": role, "unit_id": "unit-a",
    })
    assert invite.status_code == 200, invite.text
    assert client.post("/v1/auth/logout").status_code == 204
    accepted = client.post("/v1/auth/accept-invitation", json={
        "invitation_token": invite.json()["invitation_token"],
        "display_name": "Equipe F8", "password": password,
    })
    assert accepted.status_code == 200, accepted.text
    _login(client, email=email, password=password)


def test_settings_requires_session_and_exposes_owner_actions(client):
    assert client.get("/app/settings").status_code == 401
    _bootstrap(client)
    _login(client)
    response = client.get("/app/settings")
    _assert_hashed_page(response)
    for expected in (
        'id="unit-form"', 'id="persona-form"', 'id="integration-form"',
        'id="team-form"', 'id="provider-fields"',
        'type="password"', 'id="invite-token"',
        'href="/app/crm"', 'href="/app/settings"',
        "tenant_managed", "/v1/integrations/catalog", "/v1/auth/switch-unit",
    ):
        assert expected in response.text
    assert "admin-test-key" not in response.text
    assert "credential_pepper" not in response.text
    assert "X-Admin-Key" not in response.text
    assert "setInterval(" not in response.text
    home = client.get("/app")
    assert home.status_code == 200
    assert 'href="/app/settings"' in home.text


def test_viewer_sees_only_permitted_settings_without_mutation_controls(client):
    _bootstrap(client)
    _login(client)
    _invite_role(client, "viewer-settings@example.com", "viewer", VIEWER_PASSWORD)
    response = client.get("/app/settings")
    _assert_hashed_page(response)
    assert 'id="unit-form"' in response.text
    assert 'id="persona-view"' in response.text
    for blocked in (
        'id="persona-form"', 'id="integration-form"',
        'id="integration-workspace"', 'id="team-form"',
    ):
        assert blocked not in response.text
    # UI visibility is not authority: backend rejects mutation.
    forbidden = client.put("/v1/persona", json={
        "public_name": "Não permitido", "language": "pt-BR",
        "tone": "profissional", "instructions": "", "enabled": True,
    })
    assert forbidden.status_code == 403


def test_manager_reads_integration_without_secret_mutation(client):
    _bootstrap(client)
    _login(client)
    _invite_role(client, "manager-settings@example.com", "manager", MANAGER_PASSWORD)
    response = client.get("/app/settings")
    _assert_hashed_page(response)
    assert 'id="persona-form"' in response.text
    assert 'id="integration-workspace"' in response.text
    assert 'id="integration-form"' not in response.text
    assert 'id="team-form"' in response.text
    denied = client.post("/v1/integrations", json={
        "provider_key": "whatsapp_meta", "config": {}, "secrets": {},
        "source": "tenant_managed",
    })
    assert denied.status_code == 403


def test_settings_unit_switch_reloads_scoped_context(client):
    _bootstrap(client)
    _login(client)
    created = client.post("/v1/units", json={
        "unit_id": "another-unit", "display_name": "Outra Unidade",
    })
    assert created.status_code == 200
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "another-unit",
    }).status_code == 200
    response = client.get("/app/settings")
    assert response.status_code == 200
    assert 'data-unit="another-unit"' in response.text
    assert "Unidade another-unit" in response.text
    assert "Unidade unit-a" not in response.text
