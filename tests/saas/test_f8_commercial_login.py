"""F8 public login and signed human-session logout through existing endpoints."""
from __future__ import annotations

import base64
import hashlib
import re

from test_identity_rbac import OWNER_PASSWORD, _bootstrap


def _csp_script(page):
    match = re.search(r"<script>(.*?)</script>", page.text, re.DOTALL)
    assert match is not None
    digest = base64.b64encode(hashlib.sha256(
        match.group(1).encode(),
    ).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in page.headers["content-security-policy"]


def test_public_login_page_has_csp_and_no_credentials(client):
    login = client.get("/app/login")
    assert login.status_code == 200, login.text
    assert login.headers["cache-control"] == "no-store"
    assert login.headers["referrer-policy"] == "no-referrer"
    assert login.headers["x-content-type-options"] == "nosniff"
    _csp_script(login)
    assert 'id="fm-tenant"' in login.text
    assert 'id="fm-email"' in login.text
    assert 'id="fm-password"' in login.text
    assert 'type="password"' in login.text
    assert 'id="fm-unit"' in login.text
    assert 'autocomplete="current-password"' in login.text
    assert "localStorage" not in login.text
    assert "sessionStorage" not in login.text
    assert "innerHTML" not in login.text
    assert "location.assign(\"/app\")" in login.text
    assert OWNER_PASSWORD not in login.text
    assert client.get("/app").status_code == 401


def test_login_invalid_then_cookie_session_and_logout(client):
    _bootstrap(client)
    bad = client.post("/v1/auth/login", json={
        "tenant_id": "tenant-a", "email": "owner-a@example.com",
        "password": "wrong-password",
    })
    assert bad.status_code == 401
    successful = client.post("/v1/auth/login", json={
        "tenant_id": "tenant-a", "email": "owner-a@example.com",
        "password": OWNER_PASSWORD,
    })
    assert successful.status_code == 200, successful.text
    cookie = successful.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert client.get("/app").status_code == 200
    home = client.get("/app")
    _csp_script(home)
    assert 'id="fm-logout"' in home.text
    assert 'window.location.assign("/app/login")' in home.text
    assert client.post("/v1/auth/logout").status_code == 204
    assert client.get("/app").status_code == 401
    assert client.get("/app/login").status_code == 200
