"""F8 commercial shell: role-safe navigation and integrated same-origin screens."""
from __future__ import annotations

import base64
import hashlib
import re

from test_identity_rbac import (
    VIEWER_PASSWORD,
    _bootstrap,
    _login,
)

from fm_assistant.commercial_shell import (
    allowed_navigation,
    attach_navigation,
    render_home,
)
from fm_assistant.identity import Role
from fm_assistant.identity_repository import SessionPrincipal


def _principal(role=Role.OWNER, name="Operador"):
    return SessionPrincipal(
        session_id="session", user_id="user", tenant_id="tenant-a",
        unit_id="unit-a", membership_id="membership", role=role,
        email="test@example.com", display_name=name,
    )


def _script_hash(markup):
    script = re.search(r"<script>(.*?)</script>", markup, re.DOTALL)
    assert script is not None
    return base64.b64encode(hashlib.sha256(
        script.group(1).encode(),
    ).digest()).decode()


def test_home_requires_signed_human_session(client):
    assert client.get("/app").status_code == 401
    _bootstrap(client)
    _login(client)
    home = client.get("/app")
    assert home.status_code == 200, home.text
    assert home.headers["cache-control"] == "no-store"
    assert home.headers["x-content-type-options"] == "nosniff"
    assert home.headers["referrer-policy"] == "no-referrer"
    assert home.text.count('id="fm-shell"') == 1
    assert 'aria-label="Navegação principal"' in home.text
    assert 'href="/app/crm#agenda-workspace"' in home.text
    assert 'href="/app/crm#cadence-workspace"' in home.text
    assert 'href="/v1/channels/whatsapp/qr/panel"' in home.text
    assert 'id="fm-overview"' in home.text
    assert 'id="fm-reload"' in home.text
    assert '"open_opportunities"' in home.text
    assert '"/v1/knowledge/sources?page=0"' in home.text
    assert "innerHTML" not in home.text
    assert "api_key" not in home.text
    assert "secret_reference" not in home.text
    assert f"script-src 'sha256-{_script_hash(home.text)}'" in (
        home.headers["content-security-policy"]
    )


def test_shared_navigation_preserves_existing_page_csp_and_ui(client):
    _bootstrap(client)
    _login(client)
    pages = (
        "/app/crm",
        "/app/knowledge",
        "/app/inbox",
        "/v1/channels/whatsapp/qr/panel",
    )
    for page in pages:
        response = client.get(page)
        assert response.status_code == 200, (page, response.text)
        assert response.headers["cache-control"] == "no-store"
        assert response.text.count('id="fm-shell"') == 1
        assert 'href="/app"' in response.text
        assert 'aria-label="Navegação principal"' in response.text
        assert 'VendeAtendeIA' in response.text
    crm = client.get("/app/crm")
    assert 'id="agenda-workspace"' in crm.text
    assert 'id="cadence-workspace"' in crm.text
    assert f"script-src 'sha256-{_script_hash(crm.text)}'" in (
        crm.headers["content-security-policy"]
    )
    knowledge = client.get("/app/knowledge")
    assert f"script-src 'sha256-{_script_hash(knowledge.text)}'" in (
        knowledge.headers["content-security-policy"]
    )
    unavailable_plan = client.get("/v1/plan/consumption/dashboard")
    assert unavailable_plan.status_code == 403
    assert unavailable_plan.json()["detail"] == "plan_unavailable"
    whatsapp = client.get("/v1/channels/whatsapp/qr/panel")
    nonce = re.search(r'nonce="([^"]+)"', whatsapp.text)
    assert nonce is not None
    assert "script-src 'nonce-" + nonce.group(1) + "'" in (
        whatsapp.headers["content-security-policy"]
    )


def test_permission_filtered_navigation_does_not_grant_missing_access(client):
    support = _principal(Role.SUPPORT_AGENT)
    paths = [href for _, href in allowed_navigation(support)]
    assert "/app/inbox" in paths
    assert "/app/crm" not in paths
    assert "/app/knowledge" in paths
    assert "/v1/channels/whatsapp/qr/panel" not in paths
    home, csp = render_home(support)
    assert "CRM e pipeline" not in home
    assert "Plano e consumo" not in home
    assert '"open_opportunities"' not in home
    assert '"key":"inbox"' in home
    assert "script-src 'sha256-" in csp

    _bootstrap(client)
    _login(client)
    invited = client.post("/v1/users/invitations", json={
        "email": "viewer-f8@example.com", "role": "viewer",
        "unit_id": "unit-a",
    })
    assert invited.status_code == 200, invited.text
    token = invited.json()["invitation_token"]
    assert client.post("/v1/auth/logout").status_code == 204
    accepted = client.post("/v1/auth/accept-invitation", json={
        "invitation_token": token, "display_name": "Viewer F8",
        "password": VIEWER_PASSWORD,
    })
    assert accepted.status_code == 200, accepted.text
    _login(client, email="viewer-f8@example.com", password=VIEWER_PASSWORD)
    home = client.get("/app")
    assert home.status_code == 200
    assert 'href="/app/knowledge"' in home.text
    assert 'href="/app/crm"' in home.text
    assert 'href="/v1/channels/whatsapp/qr/panel"' not in home.text
    assert client.get("/v1/channels/whatsapp/qr/panel").status_code == 403


def test_shell_escapes_user_content_and_rejects_double_attachment():
    principal = _principal(name='<svg onload="alert(1)">')
    home, _ = render_home(principal)
    assert "<svg" not in home
    assert "&lt;svg" in home
    assert "onload" in home  # inert escaped text, never a rendered element
    document = '<!doctype html><html><head></head><body>Olá</body></html>'
    attached = attach_navigation(document, principal, "/app")
    assert 'id="fm-shell"' in attached
    assert '<svg onload=' not in attached
    try:
        attach_navigation(attached, principal, "/app")
    except ValueError as exc:
        assert "already_attached" in str(exc)
    else:
        raise AssertionError("Duplicate commercial navigation was allowed")
