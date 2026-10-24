"""F4 files/URL ingestion remains offline-testable and tenant-isolated."""
from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.db import (
    AuditEventORM,
    Base,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
    KnowledgeSourceVersionORM,
)
from fm_assistant.domain import TenantContext
from fm_assistant.knowledge_sources import GovernedKnowledgeSources, SourceImportDenied
from fm_assistant.knowledge_retrieval import BoundedKnowledgeRetrieval


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sources.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        engine.dispose()


def ctx(tenant="customer-a", unit="unit-a"):
    return TenantContext(tenant_id=tenant, unit_id=unit, credential_id="operator-1")


def _pdf_text():
    writer = PdfWriter()
    page = writer.add_blank_page(width=500, height=750)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }),
        }),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 30 650 Td (Contrato de suporte PDF) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def test_file_import_is_single_transaction_with_provenance_and_retrieval(store):
    sources = GovernedKnowledgeSources(store)
    result = sources.import_file(
        ctx(), filename="Condições.md", media_type="text/plain",
        content=b"Atendimento tem suporte prioritario por chat.",
        title="Manual corporativo",
    )
    assert result.source_kind == "file"
    assert result.revision == 1
    assert not result.external_source_verified
    with store() as db:
        doc = db.get(KnowledgeDocumentORM, result.document_id)
        version = db.get(KnowledgeSourceVersionORM, (result.document_id, 1))
        chunks = db.scalars(select(KnowledgeChunkORM).where(
            KnowledgeChunkORM.document_id == result.document_id,
        )).all()
        audit = db.scalars(select(AuditEventORM).where(
            AuditEventORM.resource_id == result.document_id,
        )).all()
    assert doc and doc.active
    assert version.source_kind == "file" and version.source_ref == "Condições.md"
    assert version.content_sha256 == result.content_sha256
    assert len(chunks) == result.chunks and len(audit) == 1
    assert "suporte prioritario" in BoundedKnowledgeRetrieval(store).query(
        ctx(), "suporte prioritario",
    ).context
    assert sources.list_sources(ctx())["items"][0]["document_id"] == result.document_id
    assert sources.list_sources(ctx(tenant="foreign"))["items"] == []
    assert sources.list_sources(ctx(unit="foreign"))["items"] == []


def test_csv_html_and_pdf_import_use_text_only_and_reject_binary(store):
    svc = GovernedKnowledgeSources(store)
    csv = svc.import_file(ctx(), filename="Tabela.csv", media_type="text/csv",
                          content=b"plano,limite\nAlpha,2000", title="Tabela")
    assert csv.chunks == 1
    html = svc.import_file(ctx(), filename="Pagina.html", media_type="text/html",
                           content=b"<h1>Produto Alpha</h1><script>SECRET_JS()</script>"
                                   b"<p>Valor e garantia comercial.</p>",
                           title="Pagina")
    with store() as db:
        text = db.get(KnowledgeDocumentORM, html.document_id).content
    assert "garantia comercial" in text
    assert "SECRET_JS" not in text
    pdf = svc.import_file(ctx(), filename="Manual.pdf", media_type="application/pdf",
                          content=_pdf_text(), title="Contrato PDF")
    with store() as db:
        extracted = db.get(KnowledgeDocumentORM, pdf.document_id).content
    assert "Contrato de suporte PDF" in extracted
    for name,ctype,payload in [
        ("evil.exe", "text/plain", b"not a document"),
        ("../files.txt", "text/plain", b"hello"),
        ("binary.txt", "text/plain", b"hello\x00world"),
        ("manual.txt", "text/plain", b"x" * 1_500_001),
        ("invalid.pdf", "application/pdf", b"not pdf"),
        ("wrong.txt", "application/pdf", b"hello"),
    ]:
        with pytest.raises(SourceImportDenied):
            svc.import_file(ctx(), filename=name, media_type=ctype,
                            content=payload, title="Reject")


def test_urls_allowlist_https_public_dns_no_query_no_redirect(monkeypatch, store):
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_URL_ALLOWED_HOSTS", "docs.example.com")
    visited = []
    service = GovernedKnowledgeSources(store,
        resolver=lambda host,port: ["93.184.216.34"],
        fetcher=lambda url: (visited.append(url) or
            (b"<p>Atendimento de suporte VIP.</p><script>SECRET_JS</script>", "text/html")),
    )
    result = service.import_url(ctx(), url="https://docs.example.com/planos",
                                title="Central de suporte")
    assert visited == ["https://docs.example.com/planos"]
    with store() as db:
        version = db.get(KnowledgeSourceVersionORM, (result.document_id, 1))
        document = db.get(KnowledgeDocumentORM, result.document_id)
    assert version.source_ref == "https://docs.example.com/planos"
    assert version.source_kind == "url"
    assert "SECRET_JS" not in document.content
    for url in [
        "http://docs.example.com/planos",
        "https://docs.example.com.evil.test/",
        "https://docs.example.com/planos?api_key=hidden",
        "https://owner:password@docs.example.com/",
        "https://docs.example.com:8443/",
        "https://127.0.0.1/",
        "https://localhost/",
    ]:
        with pytest.raises(SourceImportDenied):
            service.import_url(ctx(), url=url, title="Denied")
    assert len(visited) == 1
    private = GovernedKnowledgeSources(store, resolver=lambda _h,_p: ["10.0.0.5"],
                                      fetcher=lambda url: pytest.fail(url))
    with pytest.raises(SourceImportDenied, match="url_dns_denied"):
        private.import_url(ctx(), url="https://docs.example.com/planos", title="Denied")
    monkeypatch.delenv("FM_ASSISTANT_KNOWLEDGE_URL_ALLOWED_HOSTS")
    with pytest.raises(SourceImportDenied, match="url_disabled"):
        service.import_url(ctx(), url="https://docs.example.com/planos", title="Denied")


def test_failed_ingest_does_not_write_any_document_or_audit(store, monkeypatch):
    svc = GovernedKnowledgeSources(store)
    original = svc._versioning.create_source
    def fail(*args, **kwargs):
        raise RuntimeError("simulated disk rollback")
    monkeypatch.setattr(svc._versioning, "create_source", fail)
    with pytest.raises(RuntimeError):
        svc.import_file(ctx(), filename="a.txt", media_type="text/plain",
                        content=b"bounded facts", title="A")
    with store() as db:
        assert not db.scalars(select(KnowledgeDocumentORM)).all()
        assert not db.scalars(select(AuditEventORM)).all()
    monkeypatch.setattr(svc._versioning, "create_source", original)
