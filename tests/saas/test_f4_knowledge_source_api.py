"""F4 HTTP and commercial workspace tests with real authentication and SQLite."""
from __future__ import annotations

import hashlib

from fm_assistant.db import KnowledgeDocumentORM
from test_identity_rbac import _bootstrap, _login


def test_file_upload_versions_and_lists_sources_with_safe_page(client, monkeypatch):
    _bootstrap(client)
    _login(client)
    endpoint = "/v1/knowledge/sources/file"
    payload = {"title": "Plano com suporte"}
    uploaded = {"file": ("manual.txt", b"Plano Alpha inclui suporte prioritario.",
                         "text/plain")}
    assert client.post(endpoint, data=payload, files=uploaded).status_code == 503
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_SOURCES_ENABLED", "true")
    created = client.post(endpoint, data=payload, files=uploaded)
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["source_kind"] == "file"
    assert result["revision"] == 1
    assert result["chunks"] >= 1
    assert result["content_sha256"] == hashlib.sha256(
        b"Plano Alpha inclui suporte prioritario.").hexdigest()
    assert not result["external_source_verified"]
    listing = client.get("/v1/knowledge/sources")
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["document_id"] == result["document_id"]
    assert listing.json()["items"][0]["source_ref"] == "manual.txt"
    assert listing.json()["next_page"] is None
    assert client.get("/v1/knowledge/sources?page=201").status_code == 422
    assert client.delete(f"/v1/knowledge/{result['document_id']}").status_code == 204
    assert client.get("/v1/knowledge/sources").json()["items"][0]["active"] is False
    assert client.post(endpoint, headers={"Origin": "https://evil.example"},
                       data=payload, files=uploaded).status_code == 403
    assert client.post(endpoint, headers={"Sec-Fetch-Site": "cross-site"},
                       data=payload, files=uploaded).status_code == 403


def test_url_import_requires_exact_allowlist_and_does_not_touch_network_when_denied(
    client, monkeypatch,
):
    _bootstrap(client)
    _login(client)
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_SOURCES_ENABLED", "true")
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_URL_ALLOWED_HOSTS", "docs.example.com")
    sink = client.app.state.knowledge_sources
    calls = []
    monkeypatch.setattr(sink, "_resolver", lambda host,port: ["93.184.216.34"])
    monkeypatch.setattr(sink, "_fetcher", lambda url: (
        calls.append(url) or (b"<h1>Prazo Alpha</h1><p>Entrega em 12 dias.</p>",
                               "text/html"),
    ))
    endpoint = "/v1/knowledge/sources/url"
    bad = client.post(endpoint, json={
        "title": "Manual", "url": "https://docs.example.com.evil.test/a",
    })
    assert bad.status_code == 422 and not calls
    forbidden = client.post(endpoint, json={
        "title": "Manual", "url": "https://docs.example.com/path?auth=secret",
    })
    assert forbidden.status_code == 422 and not calls
    good = client.post(endpoint, json={
        "title": "Prazo de entrega", "url": "https://docs.example.com/produtos",
    })
    assert good.status_code == 201, good.text
    assert good.json()["source_kind"] == "url"
    assert calls == ["https://docs.example.com/produtos"]
    listed = client.get("/v1/knowledge/sources").json()
    assert listed["items"][0]["source_ref"] == "https://docs.example.com/produtos"
    for forged in (
        {"title": "X", "url": "https://docs.example.com/produtos", "tenant_id": "other"},
        {"title": "X", "url": "https://docs.example.com/produtos", "unit_id": "other"},
    ):
        assert client.post(endpoint, json=forged).status_code == 422
    assert len(calls) == 1


def test_management_page_requires_human_session_and_has_hashed_csp(client):
    assert client.get("/app/knowledge").status_code in (401, 403)
    _bootstrap(client)
    _login(client)
    page = client.get("/app/knowledge")
    assert page.status_code == 200, page.text
    assert page.headers["cache-control"] == "no-store"
    csp = page.headers["content-security-policy"]
    assert "script-src 'sha256-" in csp
    assert "'unsafe-inline'" not in csp.split("script-src ")[1].split(";")[0]
    assert "frame-ancestors 'none'" in csp
    assert 'id="file-form"' in page.text
    assert 'id="url-form"' in page.text
    assert 'id="preview-form"' in page.text
    assert "/v1/knowledge/sources" in page.text
    assert "/v1/knowledge/context-preview" in page.text


def test_file_upload_rejects_non_pdf_binary_and_oversize_without_db_write(
    client, monkeypatch,
):
    _bootstrap(client)
    _login(client)
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_SOURCES_ENABLED", "true")
    endpoint = "/v1/knowledge/sources/file"
    for filename,body,ctype in (
        ("private.exe", b"danger", "text/plain"),
        ("../../etc/passwd.txt", b"danger", "text/plain"),
        ("a.txt", b"invalid\x00binary", "text/plain"),
        ("a.txt", b"A" * 1_500_001, "text/plain"),
        ("a.pdf", b"%PDF-not-really", "application/pdf"),
    ):
        response=client.post(endpoint, data={"title":"Inspecao"},
                             files={"file":(filename,body,ctype)})
        assert response.status_code == 422, (filename,response.text)
    assert client.get("/v1/knowledge/sources").json()["items"] == []
