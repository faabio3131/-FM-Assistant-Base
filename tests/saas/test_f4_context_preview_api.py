"""F4 operator preview uses the same gated, tenant-isolated retrieval as the assistant."""
from __future__ import annotations


def _credential(client, provision_credential, tenant: str, unit: str) -> dict[str, str]:
    token = provision_credential(client, tenant, unit)
    return {"Authorization": f"Bearer {token}"}


def test_preview_is_opt_in_authenticated_and_returns_bounded_evidence(
    client, provision_credential, monkeypatch,
):
    auth = _credential(client, provision_credential, "customer-a", "unit-a")
    added = client.post("/v1/knowledge", headers=auth, json={
        "title": "Atendimento Alpha", "content": "Alpha inclui suporte empresarial prioritario.",
    })
    assert added.status_code == 200, added.text
    route = "/v1/knowledge/context-preview"
    payload = {"question": "Quais detalhes do suporte Alpha?"}
    inactive = client.post(route, headers=auth, json=payload)
    assert inactive.status_code == 503
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_CONTEXT_PACK_ENABLED", "true")
    response = client.post(route, headers=auth, json=payload)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["grounded"] is True
    assert result["corpus_truncated"] is False
    assert len(result["context"]) <= 4800
    assert "suporte empresarial" in result["context"]
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["document_id"] == added.json()["document_id"]
    assert result["evidence"][0]["source_revision"] is None
    assert result["evidence"][0]["current_source_verified"] is False
    assert "credential_id" not in response.text


def test_preview_uses_current_version_provenance_and_never_older_text(
    client, provision_credential, monkeypatch,
):
    auth = _credential(client, provision_credential, "customer-a", "unit-a")
    title = "Politica Alpha"
    old = "Alpha oferece um atendimento apenas por email."
    added = client.post("/v1/knowledge", headers=auth,
                        json={"title": title, "content": old})
    assert added.status_code == 200, added.text
    doc = added.json()["document_id"]
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_VERSIONING_ENABLED", "true")
    version_url = f"/v1/knowledge/{doc}/version"
    assert client.put(version_url, headers=auth, json={
        "expected_revision": 0, "title": title, "content": old,
    }).status_code == 200
    latest = client.put(version_url, headers=auth, json={
        "expected_revision": 1, "title": title,
        "content": "Alpha possui suporte prioritario por chat.",
    })
    assert latest.status_code == 200, latest.text
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_CONTEXT_PACK_ENABLED", "true")
    res = client.post("/v1/knowledge/context-preview", headers=auth,
                      json={"question": "suporte prioritario Alpha"})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["grounded"]
    assert payload["evidence"][0]["source_revision"] == 2
    assert payload["evidence"][0]["chunk_ordinal"] == 0
    assert len(payload["evidence"][0]["chunk_sha256"]) == 64
    assert "chat" in payload["context"]
    assert "apenas por email" not in payload["context"]


def test_preview_scope_and_input_boundaries_fail_closed(
    client, provision_credential, monkeypatch,
):
    first = _credential(client, provision_credential, "customer-a", "unit-a")
    foreign = _credential(client, provision_credential, "customer-b", "unit-a")
    another_unit = _credential(client, provision_credential, "customer-a", "unit-b")
    created = client.post("/v1/knowledge", headers=first, json={
        "title": "Manual Secreto", "content": "DADO-SIGILOSO de operacoes internas.",
    })
    assert created.status_code == 200
    route = "/v1/knowledge/context-preview"
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_CONTEXT_PACK_ENABLED", "true")
    for auth in (foreign, another_unit):
        response = client.post(route, headers=auth,
                               json={"question": "Manual Secreto"})
        assert response.status_code == 200
        assert response.json()["grounded"] is False
        assert "DADO-SIGILOSO" not in response.text
    for invalid in (
        {"question": "Manual Secreto", "tenant_id": "customer-a"},
        {"question": "Manual Secreto", "unit_id": "unit-a"},
        {"question": "x" * 501},
        {"question": 123},
        {"question": ""},
    ):
        assert client.post(route, headers=first, json=invalid).status_code == 422
    assert client.post(route, json={"question": "Manual Secreto"}).status_code in (401, 403)
    deleted = client.delete(
        f"/v1/knowledge/{created.json()['document_id']}", headers=first,
    )
    assert deleted.status_code == 204
    gone = client.post(route, headers=first, json={"question": "Manual Secreto"})
    assert gone.status_code == 200
    assert not gone.json()["grounded"]
