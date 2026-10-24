"""F4/WP2a: tenant-safe, auditable revocation of existing knowledge."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from fm_assistant.db import AuditEventORM, Base, KnowledgeDocumentORM
from fm_assistant.domain import TenantContext
from fm_assistant.knowledge_retrieval import BoundedKnowledgeRetrieval
from fm_assistant.repositories import KnowledgeRepository


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'revocation.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        engine.dispose()


def ctx(tenant="tenant-a", unit="unit-a", credential="manager-a"):
    return TenantContext(
        tenant_id=tenant, unit_id=unit, credential_id=credential,
    )


def test_revocation_is_atomic_audited_and_hides_source_from_retrieval(store):
    repo = KnowledgeRepository(store)
    document_id = repo.add(
        ctx(), title="Preco Alpha", content="Alpha oferece garantia de 45 dias.",
    )
    search = BoundedKnowledgeRetrieval(store)
    assert search.query(ctx(), "garantia Alpha").grounded
    assert repo.deactivate(ctx(), document_id) is True
    assert search.query(ctx(), "garantia Alpha").context == ""
    assert repo.context(ctx()) == ""
    with store() as db:
        row = db.get(KnowledgeDocumentORM, document_id)
        assert row.active is False
        events = db.scalars(select(AuditEventORM)).all()
        assert len(events) == 1
        assert events[0].action == "assistant.knowledge.deactivate"
        assert events[0].resource_id == document_id
        assert events[0].credential_id == "manager-a"
        assert events[0].tenant_id == "tenant-a"
        assert events[0].unit_id == "unit-a"
        changed = row.updated_at
    assert repo.deactivate(ctx(), document_id) is True
    with store() as db:
        assert len(db.scalars(select(AuditEventORM)).all()) == 1
        assert db.get(KnowledgeDocumentORM, document_id).updated_at == changed


def test_foreign_or_invalid_revoke_does_not_expose_or_mutate_target(store):
    repo = KnowledgeRepository(store)
    doc = repo.add(ctx(), title="Proposta", content="Proposta secreta do tenant.")
    for other in (
        ctx("tenant-b", "unit-a", "foreign"),
        ctx("tenant-a", "unit-b", "foreign"),
    ):
        assert repo.deactivate(other, doc) is False
        assert repo.context(ctx()).startswith("## Proposta")
    for malformed in ("", "x" * 65, "does-not-exist"):
        assert repo.deactivate(ctx(), malformed) is False
    with store() as db:
        assert db.get(KnowledgeDocumentORM, doc).active is True
        assert db.scalars(select(AuditEventORM)).all() == []


def test_http_scoped_knowledge_management_and_idempotency(client, provision_credential):
    owner = provision_credential(client, "owner", "sales")
    foreign = provision_credential(client, "other", "sales")
    other_unit = provision_credential(client, "owner", "different")
    key = {"Authorization": f"Bearer {owner}"}
    created = client.post(
        "/v1/knowledge", headers=key,
        json={"title": "Acordo", "content": "Acordo da unidade sales."},
    )
    assert created.status_code == 200, created.text
    doc = created.json()["document_id"]
    path = f"/v1/knowledge/{doc}"
    assert client.delete(path).status_code == 401
    assert client.delete(path, headers={"Authorization": f"Bearer {foreign}"}).status_code == 404
    assert client.delete(path, headers={"Authorization": f"Bearer {other_unit}"}).status_code == 404
    assert client.delete(path, headers=key).status_code == 204
    assert client.delete(path, headers=key).status_code == 204
    assert client.delete("/v1/knowledge/missing", headers=key).status_code == 404
