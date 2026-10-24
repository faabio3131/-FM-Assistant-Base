"""F4 final internal scenarios: scoped restoration, privacy and deterministic rerank."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.db import (
    AuditEventORM,
    Base,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
)
from fm_assistant.domain import TenantContext
from fm_assistant.knowledge_privacy import redact_knowledge_evidence
from fm_assistant.knowledge_retrieval import BoundedKnowledgeRetrieval
from fm_assistant.knowledge_sources import GovernedKnowledgeSources
from fm_assistant.repositories import KnowledgeRepository


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'final-knowledge.db'}")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


def ctx(tenant="customer-a", unit="unit-a"):
    return TenantContext(tenant_id=tenant, unit_id=unit, credential_id="operator-1")


def test_restoration_integrity_scope_idempotence_and_audit(store):
    repo = KnowledgeRepository(store)
    src = GovernedKnowledgeSources(store).import_file(
        ctx(), filename="Termos.md", media_type="text/plain",
        content=b"O produto Alpha oferece garantia de noventa dias.",
        title="Garantias Alpha",
    )
    doc = src.document_id
    assert repo.deactivate(ctx(), doc)
    assert BoundedKnowledgeRetrieval(store).query(ctx(), "garantia Alpha").context == ""
    assert not repo.reactivate(ctx("other"), doc, expected_revision=1)
    assert not repo.reactivate(ctx(unit="other"), doc, expected_revision=1)
    with pytest.raises(ValueError, match="restore_revision_conflict"):
        repo.reactivate(ctx(), doc, expected_revision=2)
    assert repo.reactivate(ctx(), doc, expected_revision=1)
    assert repo.reactivate(ctx(), doc, expected_revision=1)
    assert BoundedKnowledgeRetrieval(store).query(ctx(), "garantia Alpha").grounded
    with store() as session:
        actions = [x.action for x in session.scalars(select(AuditEventORM).where(
            AuditEventORM.resource_id == doc,
        )).all()]
    assert actions.count("assistant.knowledge.reactivate") == 1
    assert actions.count("assistant.knowledge.deactivate") == 1


def test_restoration_denies_corruption_and_unversioned_legacy(store):
    repo = KnowledgeRepository(store)
    legacy = repo.add(ctx(), title="Legado", content="Documento sem cadeia de versões.")
    repo.deactivate(ctx(), legacy)
    with pytest.raises(ValueError, match="restore_revision_conflict"):
        repo.reactivate(ctx(), legacy, expected_revision=1)
    src = GovernedKnowledgeSources(store).import_file(
        ctx(), filename="Termos.txt", media_type="text/plain",
        content=b"Alpha tem clausulas assinadas e limites comerciais.",
        title="Contrato Alpha",
    )
    repo.deactivate(ctx(), src.document_id)
    with store.begin() as session:
        chunk = session.scalar(select(KnowledgeChunkORM).where(
            KnowledgeChunkORM.document_id == src.document_id,
        ))
        chunk.content = "DADO FORJADO"
    with pytest.raises(ValueError, match="restore_integrity_denied"):
        repo.reactivate(ctx(), src.document_id, expected_revision=1)
    with store() as session:
        assert not session.get(KnowledgeDocumentORM, src.document_id).active


def test_evidence_masks_credentials_email_cpf_phone_but_preserves_original(store):
    token = "sk-abcdefghijklmno123456789"
    email = "financeiro@empresa.com.br"
    cpf = "123.456.789-09"
    phone = "+55 (11) 98888-7777"
    content = (
        f"Manual Alpha: suporte pelo contato {email}, CPF {cpf}, telefone {phone}. "
        f"Segredo técnico api_key=abcd123456 e bearer {token}. "
        "Atendimento Alpha oferece garantia em todas as compras."
    )
    doc = GovernedKnowledgeSources(store).import_file(
        ctx(), filename="Privado.md", media_type="text/plain",
        content=content.encode(), title=f"Manual Alpha {email}",
    )
    reader = BoundedKnowledgeRetrieval(store)
    found = reader.query(ctx(), "garantia atendimento Alpha")
    assert found.grounded
    assert found.evidence[0].source_revision == 1
    assert "[DADO_RESTRITO]" in found.context
    for sensitive in [token, email, cpf, phone, "abcd123456"]:
        assert sensitive not in found.context
        assert sensitive not in found.evidence[0].snippet
        assert sensitive not in found.evidence[0].title
    with store() as session:
        assert token in session.get(KnowledgeDocumentORM, doc.document_id).content
    assert "DADO_RESTRITO" in KnowledgeRepository(store).context(ctx())
    assert "[DADO_RESTRITO]" == redact_knowledge_evidence("senha: muitoSecreta")


def test_reranking_prioritizes_complete_query_coverage_and_local_chunk(store):
    repo = KnowledgeRepository(store)
    repo.add(ctx(), title="Alpha", content="Alpha " * 180)
    relevant = repo.add(
        ctx(), title="Plano Alpha Premium",
        content=("Contexto genérico do produto e sua história. " * 25)
        + "O plano Alpha inclui suporte premium prioritario e garantia ampliada. "
        + ("Texto de preenchimento sem relevancia. " * 25),
    )
    from fm_assistant.knowledge_versioning import VersionedKnowledgeIngestion

    VersionedKnowledgeIngestion(store).index_text(
        ctx(), document_id=relevant, expected_revision=0,
        title="Plano Alpha Premium",
        content=repo.context(ctx()).split("## Plano Alpha Premium\n")[1].split("\n\n## ")[0],
    )
    result = BoundedKnowledgeRetrieval(store).query(
        ctx(), "Plano Alpha suporte premium prioritario",
    )
    assert result.grounded
    assert result.evidence[0].document_id == relevant
    assert result.evidence[0].chunk_ordinal is not None
    assert "suporte premium" in result.evidence[0].snippet
    assert len(result.context) <= 4800


def test_http_restore_enforces_authority_revocation_and_scope(client, provision_credential):
    owner = provision_credential(client, "tenant-alpha", "unit-alpha")
    foreign = provision_credential(client, "tenant-beta", "unit-alpha")
    auth = {"Authorization": f"Bearer {owner}"}
    doc = client.post("/v1/knowledge", headers=auth, json={
        "title": "Política Alpha", "content": "Alpha possui suporte de garantia.",
    }).json()["document_id"]
    # An existing unversioned source is snapshotted with its original text.
    service = client.app.state.knowledge_versioning
    service.index_text(
        ctx("tenant-alpha", "unit-alpha"), document_id=doc,
        expected_revision=0, title="Política Alpha",
        content="Alpha possui suporte de garantia.",
    )
    assert client.delete(f"/v1/knowledge/{doc}", headers=auth).status_code == 204
    endpoint = f"/v1/knowledge/{doc}/reactivate?expected_revision=1"
    assert client.post(endpoint).status_code in (401, 403)
    assert client.post(endpoint, headers={
        "Authorization": f"Bearer {foreign}",
    }).status_code == 404
    assert client.post(endpoint, headers={
        **auth, "Origin": "https://forged.example",
    }).status_code == 403
    assert client.post(endpoint.replace("=1", "=2"), headers=auth).status_code == 409
    assert client.post(endpoint, headers=auth).status_code == 204
    assert client.post(endpoint, headers=auth).status_code == 204
