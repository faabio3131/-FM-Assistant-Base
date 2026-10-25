"""Real Chromium E2E against disposable FastAPI/SQLite, never production.

Covers cookie login, CRM mutation, role isolation, async failure states,
keyboard navigation and responsive layouts in a real browser.
"""
from __future__ import annotations

import socket
import threading
import time

import httpx
import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from fm_assistant.api import create_app
from fm_assistant.settings import Environment, Settings

OWNER_PASSWORD = "OwnerPassword!123"
VIEWER_PASSWORD = "ViewerPassword!123"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def site(tmp_path):
    settings = Settings(
        environment=Environment.TEST,
        database_url=f"sqlite:///{tmp_path / 'f8-browser.db'}",
        admin_key="admin-test-key",
        credential_pepper="pepper-test-very-long",
        channel_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        session_pepper="session-test-pepper-very-long-at-least-32-chars",
        session_ttl_minutes=480,
        model_backend="development",
        model_base_url=None,
        model_api_key=None,
        model_name=None,
        core_base_url=None,
        core_service_key=None,
        auto_create_schema=True,
    ).validate()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    app = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port,
        log_level="error", lifespan="on", access_log=False,
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(150):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError("F8 browser test server crashed during startup")
            time.sleep(0.1)
        else:
            raise RuntimeError("F8 browser test server was not ready")
        url = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=url, timeout=15) as api:
            response = api.post(
                "/v1/bootstrap/tenant-owner",
                headers={"X-Admin-Key": "admin-test-key"},
                json={
                    "tenant_id": "tenant-f8",
                    "tenant_name": "Empresa Browser",
                    "unit_id": "unit-f8",
                    "unit_name": "Unidade Browser",
                    "owner_email": "owner@browser.example",
                    "owner_name": "Operador Browser",
                    "password": OWNER_PASSWORD,
                    "plan_code": "trial",
                    "trial_days": 14,
                },
            )
            assert response.status_code == 200, response.text
        yield url
    finally:
        server.should_exit = True
        thread.join(timeout=12)
        if thread.is_alive():
            server.force_exit = True
            thread.join(timeout=4)


def sign_in(page, base_url, *, email="owner@browser.example",
            password=OWNER_PASSWORD):
    page.goto(base_url + "/app/login")
    page.locator("#fm-tenant").fill("tenant-f8")
    page.locator("#fm-email").fill(email)
    page.locator("#fm-password").fill(password)
    page.locator("#fm-login-submit").click()
    page.wait_for_url(base_url + "/app")
    expect(page.locator("#fm-shell")).to_be_visible()


def test_browser_login_crm_and_navigation(browser, site):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        sign_in(page, site)
        expect(page.get_by_role("heading", name="Bom trabalho, Operador Browser")).to_be_visible()
        expect(page.locator("#fm-overview")).to_have_attribute("aria-busy", "false")
        crm_link = page.get_by_role(
            "navigation", name="Navegação principal",
        ).get_by_role("link", name="CRM e pipeline")
        expect(crm_link).to_be_visible()
        crm_link.click()
        page.wait_for_url(site + "/app/crm")
        expect(page.locator("#fm-main-content")).to_be_visible()
        expect(page.locator("#crm-funnel-summary")).not_to_be_empty()
        page.locator("#contact-name").fill("Cliente Browser E2E")
        page.locator("#contact-email").fill("browser-test@example.com")
        page.get_by_role("button", name="Cadastrar contato").click()
        expect(page.locator("#contacts")).to_contain_text("Cliente Browser E2E")
        page.locator("#opportunity-contact").select_option(label="Cliente Browser E2E")
        page.locator("#opportunity-title").fill("Proposta via navegador")
        page.locator("#amount-cents").fill("24000")
        page.get_by_role("button", name="Abrir oportunidade").click()
        expect(page.locator("#opportunities")).to_contain_text("Proposta via navegador")
        page.get_by_role("link", name="Agenda", exact=True).click()
        expect(page.locator("#agenda-workspace")).to_be_visible()
        page.get_by_role("link", name="Cadências", exact=True).click()
        expect(page.locator("#cadence-workspace")).to_be_visible()
        page.goto(site + "/app/knowledge")
        expect(page.locator("#fm-shell")).to_be_visible()
        page.goto(site + "/app/settings")
        expect(page.locator("#persona-form")).to_be_visible()
        assert errors == [], errors
    finally:
        context.close()


def test_browser_empty_partial_forbidden_unavailable_and_session_expiry(browser, site):
    context = browser.new_context()
    page = context.new_page()
    try:
        sign_in(page, site)
        page.route("**/v1/crm/analytics", lambda route: route.fulfill(
            status=503, content_type="application/json",
            body='{"detail":"provider_unavailable"}',
        ))
        page.route("**/v1/knowledge/sources?page=0", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"items":[{"document_id":"sample"}],"next_page":1}',
        ))
        page.route("**/v1/inbox?page=0&limit=50", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"items":[],"next_page":null}',
        ))
        page.locator("#fm-reload").click()
        expect(page.locator("#fm-overview")).to_have_attribute("aria-busy", "false")
        expect(page.locator('[data-state="unavailable"]')).to_have_count(1)
        expect(page.locator('[data-state="partial"]')).to_have_count(1)
        expect(page.locator('[data-state="empty"]')).to_have_count(2)
        expect(page.locator("#fm-status")).to_contain_text("Consulta parcial")
        page.unroute("**/v1/crm/analytics")
        page.route("**/v1/crm/analytics", lambda route: route.fulfill(
            status=403, content_type="application/json",
            body='{"detail":"permission_required"}',
        ))
        page.locator("#fm-reload").click()
        expect(page.locator('[data-state="forbidden"]')).to_have_count(1)
        page.unroute("**/v1/crm/analytics")
        page.route("**/v1/crm/analytics", lambda route: route.fulfill(
            status=401, content_type="application/json",
            body='{"detail":"expired"}',
        ))
        page.locator("#fm-reload").click()
        expect(page.locator('[data-state="unauthorized"]')).to_have_count(1)
        expect(page.get_by_role("link", name="Entrar novamente")).to_be_visible()
        expect(page.locator("#fm-status")).to_contain_text("Sessão expirada")
        page.get_by_role("button", name="Sair da conta").click()
        page.wait_for_url(site + "/app/login")
        assert context.request.get(site + "/app").status == 401
    finally:
        context.close()


def test_browser_mobile_keyboard_and_landmarks(browser, site):
    context = browser.new_context(viewport={"width": 320, "height": 720})
    page = context.new_page()
    try:
        page.goto(site + "/app/login")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        sign_in(page, site)
        for width in (320, 375, 768, 1280):
            page.set_viewport_size({"width": width, "height": 800})
            for path in ("/app", "/app/settings"):
                page.goto(site + path)
                expect(page.locator("#fm-shell")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (
                    path, width,
                    page.evaluate("document.documentElement.scrollWidth"),
                )
                assert page.locator("#fm-main-content").count() == 1
                assert page.locator('a[href="#fm-main-content"]').count() == 1
        page.goto(site + "/app")
        page.keyboard.press("Tab")
        expect(page.locator(".fm-skip")).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#fm-main-content")).to_be_visible()
    finally:
        context.close()


def test_browser_viewer_has_no_integration_management(browser, site):
    with httpx.Client(base_url=site, timeout=15) as api:
        assert api.post("/v1/auth/login", json={
            "tenant_id": "tenant-f8", "email": "owner@browser.example",
            "password": OWNER_PASSWORD,
        }).status_code == 200
        invitation = api.post("/v1/users/invitations", json={
            "email": "viewer@browser.example", "role": "viewer", "unit_id": "unit-f8",
        })
        assert invitation.status_code == 200, invitation.text
        assert api.post("/v1/auth/logout").status_code == 204
        accepted = api.post("/v1/auth/accept-invitation", json={
            "invitation_token": invitation.json()["invitation_token"],
            "display_name": "Viewer Browser", "password": VIEWER_PASSWORD,
        })
        assert accepted.status_code == 200, accepted.text
    context = browser.new_context()
    page = context.new_page()
    try:
        sign_in(page, site, email="viewer@browser.example", password=VIEWER_PASSWORD)
        expect(page.get_by_role("link", name="WhatsApp")).to_have_count(0)
        page.goto(site + "/app/settings")
        expect(page.locator("#persona-form")).to_have_count(0)
        expect(page.locator("#integration-form")).to_have_count(0)
        response = page.goto(site + "/v1/channels/whatsapp/qr/panel")
        assert response is not None and response.status == 403
    finally:
        context.close()
