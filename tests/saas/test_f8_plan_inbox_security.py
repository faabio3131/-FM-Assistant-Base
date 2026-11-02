"""F8 plan hub + inbox CSP: session, fail-closed states and script integrity."""
from __future__ import annotations

import base64
import hashlib
import re

from test_identity_rbac import _bootstrap, _login
from test_plan_consumption_view import _plan


def _assert_hashed_script(response):
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src ", 1)[1].split(";", 1)[0]
    scripts = re.findall(r"<script>(.*?)</script>", response.text, re.DOTALL)
    assert len(scripts) == 1
    digest = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in csp
    assert "innerHTML" not in response.text
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text


def test_customer_plan_page_no_projection_and_no_scope_override(client):
    assert client.get("/app/plan").status_code == 401
    _bootstrap(client)
    _login(client)
    page = client.get("/app/plan?tenant_id=foreign&unit_id=other")
    _assert_hashed_script(page)
    assert page.text.count('id="fm-shell"') == 1
    assert 'class="fm-tab" href="/app/plan" aria-current="page"' in page.text
    assert 'id="fm-plan-status"' in page.text
    assert 'id="fm-plan-rows"' in page.text
    assert 'id="fm-plan-detail"' in page.text
    assert "plan_unavailable" in page.text
    assert '"/v1/plan/consumption"' in page.text
    assert '"/v1/entitlements"' in page.text
    assert 'id="fm-main-content"' in page.text
    assert "private_provider_cost" not in page.text
    assert "secret_reference" not in page.text
    assert client.get("/v1/plan/consumption").status_code == 403


def test_customer_plan_hub_reuses_authenticated_plan_projection(client):
    _bootstrap(client)
    _plan(client, "tenant-a", revision=1, cap=9000)
    _login(client)
    page = client.get("/app/plan")
    _assert_hashed_script(page)
    plan = client.get("/v1/plan/consumption")
    assert plan.status_code == 200
    assert plan.json()["plan_name"] == "Franquia 1"
    assert plan.json()["usage_verified"] is False
    assert all(row["remaining_units"] is None for row in plan.json()["consumption"])
    assert "ai.cost_usd_microunits" not in plan.text
    assert "Saldo não verificado" in page.text
    assert "usage_verified" in page.text
    assert "private_cost" not in page.text
    assert 'href="/app/plan"' in client.get("/app").text
    detailed = client.get("/v1/plan/consumption/dashboard")
    assert detailed.status_code == 200


def test_customer_plan_page_denies_non_billing_role(client):
    _bootstrap(client)
    _login(client)
    invite = client.post("/v1/users/invitations", json={
        "email": "support-plan@example.com", "role": "support_agent",
        "unit_id": "unit-a",
    })
    assert invite.status_code == 200, invite.text
    token = invite.json()["invitation_token"]
    assert client.post("/v1/auth/logout").status_code == 204
    accepted = client.post("/v1/auth/accept-invitation", json={
        "invitation_token": token,
        "display_name": "Support Plan",
        "password": "SupportPassword!123",
    })
    assert accepted.status_code == 200, accepted.text
    _login(client, email="support-plan@example.com", password="SupportPassword!123")
    home = client.get("/app")
    assert home.status_code == 200
    assert 'href="/app/plan"' not in home.text
    assert client.get("/app/plan").status_code == 403
    assert client.get("/v1/plan/consumption").status_code == 403


def test_inbox_hashed_csp_and_existing_controls(client):
    assert client.get("/app/inbox").status_code == 401
    _bootstrap(client)
    _login(client)
    response = client.get("/app/inbox")
    _assert_hashed_script(response)
    assert response.text.count('id="fm-main-content"') == 1
    assert response.text.count('href="#fm-main-content"') == 1
    assert 'id="queue"' in response.text
    assert 'id="transcript"' in response.text
    assert 'id="reply-panel"' in response.text
    assert 'id="fm-shell"' in response.text
    assert "setInterval(" in response.text
    assert "connect-src 'self'" in response.headers["content-security-policy"]
