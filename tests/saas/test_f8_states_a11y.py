"""F8 states and accessible layout contracts across commercial modules."""
from __future__ import annotations

from test_identity_rbac import _bootstrap, _login


def test_home_has_explicit_async_states_and_scope_navigation(client):
    _bootstrap(client)
    _login(client)
    page = client.get("/app")
    assert page.status_code == 200
    assert 'aria-busy' in page.text
    assert '"empty"' in page.text
    assert '"partial"' in page.text
    assert '"unauthorized"' in page.text
    assert '"forbidden"' in page.text
    assert '"unavailable"' in page.text
    assert "Sem registros" in page.text
    assert "Entrar novamente" in page.text
    assert 'href="#fm-main-content"' in page.text
    assert 'id="fm-main-content"' in page.text
    assert 'aria-current="page"' in page.text
    assert 'loginLink.href = "/app/login"' in page.text
    assert "innerHTML" not in page.text

    crm = client.get("/app/crm")
    assert crm.status_code == 200
    assert ': "/v1/crm/opportunities")' in crm.text
    assert '"stage-filter").value' in crm.text


def test_skip_link_and_mobile_layout_are_shared_without_modifying_page_scripts(client):
    _bootstrap(client)
    _login(client)
    for url in (
        "/app/settings", "/app/crm", "/app/knowledge", "/app/inbox",
        "/v1/channels/whatsapp/qr/panel",
    ):
        page = client.get(url)
        assert page.status_code == 200, (url, page.text)
        assert page.text.count('id="fm-main-content"') == 1
        assert page.text.count('href="#fm-main-content"') == 1
        assert page.text.count('id="fm-shell"') == 1
        assert ".fm-skip:focus" in page.text
    crm = client.get("/app/crm")
    assert 'class="fm-tab" href="/app/crm" aria-current="page"' in crm.text
    settings = client.get("/app/settings")
    assert "minmax(min(100%,320px),1fr)" in settings.text
    assert "@media(max-width:480px)" in settings.text
    login = client.get("/app/login")
    assert login.status_code == 200
    assert 'id="fm-main-content"' in login.text
