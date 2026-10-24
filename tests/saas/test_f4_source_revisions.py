"""F4 governed source replacement remains CAS, scoped, immutable and auditable."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_identity_rbac import _bootstrap, _login

from fm_assistant.db import (
    AuditEventORM,
    Base,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
    KnowledgeSourceVersionORM,
)
from fm_assistant.domain import TenantContext
from fm_assistant.knowledge_retrieval import BoundedKnowledgeRetrieval
from fm_assistant.knowledge_sources import GovernedKnowledgeSources, SourceImportDenied
from fm_assistant.knowledge_versioning import KnowledgeVersionDenied, VersionedKnowledgeIngestion


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'source-revisions.db'}")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


def ctx(tenant="tenant-a", unit="unit-a"):
    return TenantContext(tenant_id=tenant, unit_id=unit, credential_id="operator-1")


def test_file_replacement_preserves_identity_provenance_history_and_noop(store):
    service = GovernedKnowledgeSources(store)
    original = service.import_file(
        ctx(), filename="Oferta.md", media_type="text/plain",
        content=b"Plano Alpha possui apenas email.", title="Oferta Alpha",
    )
    replaced = service.replace_file(
        ctx(), document_id=original.document_id, expected_revision=1,
        filename="Oferta.md", media_type="text/plain",
        content=b"Plano Alpha possui chat prioritario.", title="Oferta Alpha",
    )
    assert replaced.document_id == original.document_id
    assert replaced.revision == 2 and replaced.indexed
    assert replaced.source_kind == "file"
    old = service.list_sources(ctx())
    assert len(old["items"]) == 1
    assert old["items"][0]["revision"] == 2
    assert old["items"][0]["source_ref"] == "Oferta.md"
    assert old["items"][0]["content_sha256"] == replaced.content_sha256
    with store() as db:
        versions = db.scalars(select(KnowledgeSourceVersionORM).where(
            KnowledgeSourceVersionORM.document_id == original.document_id,
        ).order_by(KnowledgeSourceVersionORM.revision)).all()
        chunks = db.scalars(select(KnowledgeChunkORM).where(
            KnowledgeChunkORM.document_id == original.document_id,
        ).order_by(KnowledgeChunkORM.revision)).all()
        audits = db.scalars(select(AuditEventORM).where(
            AuditEventORM.resource_id == original.document_id,
        )).all()
    assert [(x.revision, x.source_kind, x.source_ref) for x in versions] == [
        (1, "file", "Oferta.md"), (2, "file", "Oferta.md"),
    ]
    assert len(audits) == 2
    assert "apenas email" in chunks[0].content
    assert "chat prioritario" in chunks[1].content
    current = BoundedKnowledgeRetrieval(store).query(ctx(), "chat prioritario Alpha")
    assert current.grounded and current.evidence[0].source_revision == 2
    assert "apenas email" not in current.context
    noop = service.replace_file(
        ctx(), document_id=original.document_id, expected_revision=2,
        filename="Oferta.md", media_type="text/plain",
        content=b"Plano Alpha possui chat prioritario.", title="Oferta Alpha",
    )
    assert not noop.indexed and noop.revision == 2
    with store() as db:
        assert len(db.scalars(select(AuditEventORM).where(
            AuditEventORM.resource_id == original.document_id,
        )).all()) == 2


def test_file_replacement_rejects_cross_scope_stale_mismatch_and_forged_content(store):
    service = GovernedKnowledgeSources(store)
    original = service.import_file(
        ctx(), filename="Termos.txt", media_type="text/plain",
        content=b"Condicoes contratuais vigentes.", title="Termos",
    )
    params = {
        "document_id": original.document_id,
        "expected_revision": 1,
        "filename": "Termos.txt", "media_type": "text/plain",
        "content": b"Atualizacao segura.", "title": "Termos",
    }
    for caller in (ctx("foreign"), ctx(unit="foreign")):
        with pytest.raises(SourceImportDenied, match="source_not_found"):
            service.replace_file(caller, **params)
    with pytest.raises(SourceImportDenied, match="source_not_found"):
        service.replace_file(ctx(), **{**params, "filename": "Outro.txt"})
    with pytest.raises(SourceImportDenied, match="stale_revision"):
        service.replace_file(ctx(), **{**params, "expected_revision": 2})
    with pytest.raises(KnowledgeVersionDenied, match="source_provenance_mismatch"):
        VersionedKnowledgeIngestion(store).index_text(
            ctx(), document_id=original.document_id, expected_revision=1,
            title="Termos", content="Tentativa de desclassificar importacao.",
        )
    with store() as db:
        doc = db.get(KnowledgeDocumentORM, original.document_id)
        doc.content = "Alteracao fora do mecanismo de versoes."
        db.commit()
    with pytest.raises(KnowledgeVersionDenied, match="source_integrity_mismatch"):
        service.replace_file(ctx(), **params)
    with store() as db:
        versions = db.scalars(select(KnowledgeSourceVersionORM).where(
            KnowledgeSourceVersionORM.document_id == original.document_id,
        )).all()
    assert len(versions) == 1


def test_url_refresh_preserves_original_url_and_skips_network_on_rejected_preflight(
    store, monkeypatch,
):
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_URL_ALLOWED_HOSTS", "docs.example.com")
    calls = []
    content = [b"Plano Alpha garante resposta em 48 horas."]
    service = GovernedKnowledgeSources(
        store, resolver=lambda host, port: ["93.184.216.34"],
        fetcher=lambda url, addresses: (
            calls.append((url, addresses)) or (content[0], "text/plain")
        ),
    )
    url = "https://docs.example.com/termos"
    first = service.import_url(ctx(), url=url, title="Politica Alpha")
    assert first.revision == 1
    before = len(calls)
    for caller, revision, tested_url in [
        (ctx(tenant="foreign"), 1, url),
        (ctx(unit="foreign"), 1, url),
        (ctx(), 5, url),
        (ctx(), 1, "https://docs.example.com/outro"),
    ]:
        with pytest.raises(SourceImportDenied):
            service.refresh_url(caller, document_id=first.document_id,
                                expected_revision=revision, title="Politica Alpha",
                                url=tested_url)
    assert len(calls) == before
    content[0] = b"Plano Alpha garante resposta em 12 horas."
    updated = service.refresh_url(
        ctx(), document_id=first.document_id, expected_revision=1,
        url=url, title="Politica Alpha",
    )
    assert updated.document_id == first.document_id
    assert updated.revision == 2 and updated.indexed
    assert calls[-1][1] == ("93.184.216.34",)
    again = service.refresh_url(
        ctx(), document_id=first.document_id, expected_revision=2,
        url=url, title="Politica Alpha",
    )
    assert again.revision == 2 and not again.indexed
    with store() as db:
        versions = db.scalars(select(KnowledgeSourceVersionORM).where(
            KnowledgeSourceVersionORM.document_id == first.document_id,
        ).order_by(KnowledgeSourceVersionORM.revision)).all()
    assert [(v.revision, v.source_kind, v.source_ref) for v in versions] == [
        (1, "url", url), (2, "url", url),
    ]


def test_file_replace_http_cas_permission_and_management_ui(client, monkeypatch):
    _bootstrap(client)
    _login(client)
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_SOURCES_ENABLED", "true")
    original = client.post(
        "/v1/knowledge/sources/file", data={"title": "Manual A"},
        files={"file": ("manual.txt", b"Plano A tem 20 consultas.", "text/plain")},
    )
    assert original.status_code == 201, original.text
    doc = original.json()["document_id"]
    endpoint = f"/v1/knowledge/sources/{doc}/file"
    payload = {"title": "Manual A", "expected_revision": "1"}
    files = {"file": ("manual.txt", b"Plano A tem 50 consultas.", "text/plain")}
    bad_scope = client.put(endpoint, headers={"Sec-Fetch-Site": "cross-site"},
                           data=payload, files=files)
    assert bad_scope.status_code == 403
    updated = client.put(endpoint, data=payload, files=files)
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == 2
    assert updated.json()["indexed"] is True
    assert updated.json()["document_id"] == doc
    stale = client.put(endpoint, data=payload, files=files)
    assert stale.status_code == 409
    mismatch = client.put(endpoint, data={"title": "Manual A", "expected_revision": "2"},
                          files={"file": ("another.txt", b"malicious", "text/plain")})
    assert mismatch.status_code == 404
    forged = client.put(endpoint, data={
        "title": "Manual A", "expected_revision": "3", "tenant_id": "forged",
    }, files=files)
    assert forged.status_code in (409, 422)
    no_op = client.put(
        endpoint, data={"title": "Manual A", "expected_revision": "2"}, files=files,
    )
    assert no_op.status_code == 200 and no_op.json()["indexed"] is False
    assert client.get("/v1/knowledge/sources").json()["items"][0]["revision"] == 2
    page = client.get("/app/knowledge")
    assert page.status_code == 200
    assert "Substituir mantendo histórico" in page.text
    assert "Atualizar conteúdo desta URL" in page.text
    assert "result.indexed" in page.text
    assert "sha256-" in page.headers["content-security-policy"]
    assert client.delete(f"/v1/knowledge/{doc}").status_code == 204
    assert client.put(endpoint, data={"title": "Manual A", "expected_revision": "2"},
                      files=files).status_code == 404


def test_url_refresh_http_is_gated_and_revision_aware(client, monkeypatch):
    _bootstrap(client)
    _login(client)
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_SOURCES_ENABLED", "true")
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_URL_ALLOWED_HOSTS", "docs.example.com")
    source = client.app.state.knowledge_sources
    counter = [0]
    monkeypatch.setattr(source, "_resolver", lambda host, port: ["93.184.216.34"])
    def fetch(url, addresses):
        counter[0] += 1
        return (f"Atualizacao {counter[0]} sobre atendimento Alpha.".encode(), "text/plain")
    monkeypatch.setattr(source, "_fetcher", fetch)
    url = "https://docs.example.com/alpha"
    created = client.post("/v1/knowledge/sources/url", json={
        "title": "Atendimento", "url": url,
    })
    assert created.status_code == 201
    doc = created.json()["document_id"]
    endpoint = f"/v1/knowledge/sources/{doc}/url"
    denied = client.put(endpoint, json={
        "title": "Atendimento", "url": url, "expected_revision": 0,
    })
    assert denied.status_code == 422 and counter[0] == 1
    old = client.put(endpoint, json={
        "title": "Atendimento", "url": url, "expected_revision": 4,
    })
    assert old.status_code == 409 and counter[0] == 1
    update = client.put(endpoint, json={
        "title": "Atendimento", "url": url, "expected_revision": 1,
    })
    assert update.status_code == 200 and update.json()["revision"] == 2
    assert counter[0] == 2
    forged = client.put(endpoint, json={
        "title": "Atendimento", "url": url, "expected_revision": 2,
        "tenant_id": "foreign",
    })
    assert forged.status_code == 422 and counter[0] == 2
    blocked = client.put(endpoint, headers={"Origin": "https://evil.example"}, json={
        "title": "Atendimento", "url": url, "expected_revision": 2,
    })
    assert blocked.status_code == 403
    assert counter[0] == 2
    assert client.get("/v1/knowledge/sources").json()["items"][0]["revision"] == 2
