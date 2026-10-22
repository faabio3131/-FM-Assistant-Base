"""F4 text ingest versions + immutable deterministic chunks; no provider or URL calls."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.db import (
    Base, KnowledgeChunkORM, KnowledgeDocumentORM, KnowledgeSourceVersionORM,
)
from fm_assistant.domain import TenantContext
from fm_assistant.knowledge_versioning import (
    KnowledgeVersionDenied, VersionedKnowledgeIngestion, split_knowledge_chunks,
)
from fm_assistant.repositories import KnowledgeRepository


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'versions.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        engine.dispose()


def context(tenant="customer-a", unit="unit-a"):
    return TenantContext(tenant_id=tenant, unit_id=unit, credential_id="synthetic-owner")


def test_first_update_requires_immutable_legacy_snapshot(store):
    repo = KnowledgeRepository(store)
    doc = repo.add(context(), title="Serviço A", content="Servico A com suporte humano.")
    ingestion = VersionedKnowledgeIngestion(store)
    with pytest.raises(KnowledgeVersionDenied, match="bootstrap_existing_first"):
        ingestion.index_text(context(), document_id=doc, expected_revision=0,
                             title="Serviço A", content="Servico A com preco novo.")
    first = ingestion.index_text(
        context(), document_id=doc, expected_revision=0,
        title="Serviço A", content="Servico A com suporte humano.",
    )
    assert first.revision == 1 and first.indexed
    assert first.external_source_verified is False
    original = ingestion.index_text(
        context(), document_id=doc, expected_revision=1,
        title="Serviço A", content="Servico A com suporte humano.",
    )
    assert original.indexed is False and original.revision == 1
    second = ingestion.index_text(
        context(), document_id=doc, expected_revision=1,
        title="Serviço A", content="Servico A com preco novo.",
    )
    assert second.indexed is True and second.revision == 2
    with store() as db:
        versions = db.scalars(select(KnowledgeSourceVersionORM).where(
            KnowledgeSourceVersionORM.document_id == doc,
        ).order_by(KnowledgeSourceVersionORM.revision)).all()
        assert [v.revision for v in versions] == [1, 2]
        assert versions[0].content_sha256 == hashlib.sha256(
            b"Servico A com suporte humano.").hexdigest()
        rows = db.scalars(select(KnowledgeChunkORM).where(
            KnowledgeChunkORM.document_id == doc,
            KnowledgeChunkORM.revision == 1,
        )).all()
        assert "".join(item.content for item in rows) == "Servico A com suporte humano."
        legacy = db.get(KnowledgeDocumentORM, doc)
        assert legacy.content == "Servico A com preco novo."


def test_scope_and_revision_fail_closed_without_mutating(store):
    repo = KnowledgeRepository(store)
    doc = repo.add(context(), title="Plano", content="Plano empresarial com SLA.")
    ingestion = VersionedKnowledgeIngestion(store)
    for scope in (context(tenant="tenant-foreign"), context(unit="unit-foreign")):
        with pytest.raises(KnowledgeVersionDenied, match="document_scope_denied"):
            ingestion.index_text(scope, document_id=doc, expected_revision=0,
                                 title="Plano", content="Plano empresarial com SLA.")
    one = ingestion.index_text(context(), document_id=doc, expected_revision=0,
                               title="Plano", content="Plano empresarial com SLA.")
    for bad_rev in (-1, True, 0, 100):
        with pytest.raises(KnowledgeVersionDenied):
            ingestion.index_text(context(), document_id=doc, expected_revision=bad_rev,
                                 title="Plano", content="Nova versão")
    with store() as db:
        n = db.scalar(select(func.count(KnowledgeSourceVersionORM.revision)))
        assert n == 1
        assert one.revision == 1


def test_deterministic_bounded_chunk_offsets_and_hashes(store):
    text = "A" * 1700 + "B" * 23
    chunks = split_knowledge_chunks(text)
    assert chunks[0][:2] == (0, 800)
    assert chunks[1][:2] == (700, 1500)
    assert chunks[2][:2] == (1400, 1723)
    assert len(chunks) == 3
    assert all(text[start:end] == snippet for start, end, snippet in chunks)
    doc = KnowledgeRepository(store).add(context(), title="Contrato", content=text)
    VersionedKnowledgeIngestion(store).index_text(
        context(), document_id=doc, expected_revision=0,
        title="Contrato", content=text,
    )
    with store() as db:
        persisted = db.scalars(select(KnowledgeChunkORM).where(
            KnowledgeChunkORM.document_id == doc,
        ).order_by(KnowledgeChunkORM.ordinal)).all()
        assert len(persisted) == 3
        assert all(row.content_sha256 == hashlib.sha256(
            row.content.encode()).hexdigest() for row in persisted)


def test_active_only_and_input_limits(store):
    repo = KnowledgeRepository(store)
    doc = repo.add(context(), title="A", content="B")
    with store.begin() as db:
        row = db.get(KnowledgeDocumentORM, doc)
        row.active = False
    svc = VersionedKnowledgeIngestion(store)
    with pytest.raises(KnowledgeVersionDenied, match="document_scope_denied"):
        svc.index_text(context(), document_id=doc, expected_revision=0,
                       title="A", content="B")
    for content in ("", "x" * 24_001):
        with pytest.raises(KnowledgeVersionDenied):
            split_knowledge_chunks(content)


def test_authenticated_existing_knowledge_endpoint_and_new_version_route(
    client, provision_credential, monkeypatch,
):
    key_a = provision_credential(client, "tenant-knowledge-a", "unit-knowledge")
    key_b = provision_credential(client, "tenant-knowledge-b", "unit-knowledge")
    auth_a = {"Authorization": f"Bearer {key_a}"}
    auth_b = {"Authorization": f"Bearer {key_b}"}
    source = client.post("/v1/knowledge", headers=auth_a,
                         json={"title": "Cardapio", "content": "Produtos do dia."})
    assert source.status_code == 200, source.text
    doc_id = source.json()["document_id"]
    path = f"/v1/knowledge/{doc_id}/version"
    payload = {"expected_revision": 0, "title": "Cardapio",
               "content": "Produtos do dia."}
    assert client.put(path, headers=auth_a, json=payload).status_code == 503
    monkeypatch.setenv("FM_ASSISTANT_KNOWLEDGE_VERSIONING_ENABLED", "true")
    assert client.put(path, headers=auth_b, json=payload).status_code == 409
    boot = client.put(path, headers=auth_a, json=payload)
    assert boot.status_code == 200, boot.text
    assert boot.json()["revision"] == 1
    assert boot.json()["external_source_verified"] is False
    duplicate = client.put(path, headers=auth_a, json={
        **payload, "expected_revision": 1,
    })
    assert duplicate.status_code == 200 and duplicate.json()["indexed"] is False
    updated = client.put(path, headers=auth_a, json={
        "expected_revision": 1, "title": "Cardapio",
        "content": "Produtos do dia com entrega.",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == 2
    assert client.put(path, headers=auth_a, json={
        "expected_revision": 1, "title": "Cardapio",
        "content": "Produtos diferentes",
    }).status_code == 409
    assert client.put(path, headers=auth_a, json={
        "expected_revision": True, "title": "Cardapio",
        "content": "Produtos do dia.",
    }).status_code == 422
    monkeypatch.delenv("FM_ASSISTANT_KNOWLEDGE_VERSIONING_ENABLED")


def test_alembic_migrates_existing_document_without_rewriting_content(tmp_path):
    url = f"sqlite:///{tmp_path / 'versions-upgrade.db'}"
    env = os.environ.copy()
    env["FM_ASSISTANT_DATABASE_URL"] = url
    def upgrade(revision):
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision],
                       cwd=os.getcwd(), env=env, check=True,
                       capture_output=True, text=True)
    upgrade("20261020_0019")
    engine = create_engine(url)
    try:
        with engine.begin() as db:
            db.exec_driver_sql(
                "INSERT INTO assistant_knowledge_documents "
                "(document_id,tenant_id,unit_id,title,content,active,created_at,updated_at) "
                "VALUES ('d1','tenant-a','unit-a','Original','Dados antigos',1,"
                "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        upgrade("head")
        with engine.connect() as db:
            original = db.exec_driver_sql(
                "SELECT title, content FROM assistant_knowledge_documents "
                "WHERE document_id='d1'"
            ).one()
            assert tuple(original) == ("Original", "Dados antigos")
            assert db.exec_driver_sql(
                "SELECT count(*) FROM assistant_knowledge_source_versions"
            ).scalar_one() == 0
            assert db.exec_driver_sql(
                "SELECT count(*) FROM assistant_knowledge_chunks"
            ).scalar_one() == 0
    finally:
        engine.dispose()
