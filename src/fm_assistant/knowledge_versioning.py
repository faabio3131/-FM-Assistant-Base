"""F4 controlled versioning of existing knowledge documents (text-only WP).

Always append a complete immutable revision and chunks in the same database
transaction. Existing unversioned documents MUST first be snapshotted
unchanged, so an update never erases an unknown historical original.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from .db import AuditEventORM, KnowledgeChunkORM, KnowledgeDocumentORM, KnowledgeSourceVersionORM
from .domain import TenantContext

_MAX_CONTENT = 24_000
_CHUNK_SIZE = 800
_OVERLAP = 100
_MAX_CHUNKS = 64
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class KnowledgeVersionDenied(ValueError):
    pass


@dataclass(frozen=True)
class KnowledgeVersionResult:
    document_id: str
    revision: int
    chunks: int
    content_sha256: str
    indexed: bool
    external_source_verified: bool = False


def split_knowledge_chunks(content: str) -> tuple[tuple[int, int, str], ...]:
    if not isinstance(content, str) or not content.strip() or len(content) > _MAX_CONTENT:
        raise KnowledgeVersionDenied("f4.content_invalid")
    parts: list[tuple[int, int, str]] = []
    start = 0
    while start < len(content):
        end = min(start + _CHUNK_SIZE, len(content))
        parts.append((start, end, content[start:end]))
        if len(parts) > _MAX_CHUNKS:
            raise KnowledgeVersionDenied("f4.chunk_limit")
        if end == len(content):
            break
        start = end - _OVERLAP
    return tuple(parts)


class VersionedKnowledgeIngestion:
    def __init__(self, sessions) -> None:
        self._sessions = sessions

    def create_source(
        self, context: TenantContext, *, title: str, content: str,
        source_kind: str, source_ref: str,
    ) -> KnowledgeVersionResult:
        """Create document + immutable revision + chunks + audit in one TX.

        Never use KnowledgeRepository.add followed by index_text: if a later
        chunk write fails the first operation would leave a false import.
        """
        if (source_kind not in {"file", "url"} or not isinstance(source_ref, str)
                or not 1 <= len(source_ref) <= 512
                or not isinstance(title, str) or not 1 <= len(title.strip()) <= 255
                or not isinstance(content, str) or not content.strip()
                or len(content) > _MAX_CONTENT
                or not context.tenant_id or not context.unit_id
                or not context.credential_id or len(context.credential_id) > 64):
            raise KnowledgeVersionDenied("f4.source_invalid")
        title, content = title.strip(), content.strip()
        chunks = split_knowledge_chunks(content)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)
        document_id = str(uuid4())
        with self._sessions.begin() as db:
            db.add(KnowledgeDocumentORM(
                document_id=document_id, tenant_id=context.tenant_id,
                unit_id=context.unit_id, title=title, content=content,
                active=True, created_at=now, updated_at=now,
            ))
            db.add(KnowledgeSourceVersionORM(
                document_id=document_id, revision=1,
                tenant_id=context.tenant_id, unit_id=context.unit_id,
                title=title, content_sha256=digest, source_kind=source_kind,
                source_ref=source_ref, actor_credential_id=context.credential_id,
                created_at=now,
            ))
            for ordinal, (begin, end, chunk) in enumerate(chunks):
                db.add(KnowledgeChunkORM(
                    document_id=document_id, revision=1, ordinal=ordinal,
                    tenant_id=context.tenant_id, unit_id=context.unit_id,
                    start_offset=begin, end_offset=end, content=chunk,
                    content_sha256=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                    created_at=now,
                ))
            db.add(AuditEventORM(
                audit_id=str(uuid4()), tenant_id=context.tenant_id,
                unit_id=context.unit_id, credential_id=context.credential_id,
                action="assistant.knowledge.source_import",
                resource_type="assistant_knowledge", resource_id=document_id,
                outcome="success",
                metadata_json='{"source_kind":"' + source_kind + '"}',
                created_at=now,
            ))
        return KnowledgeVersionResult(
            document_id=document_id, revision=1, chunks=len(chunks),
            content_sha256=digest, indexed=True,
        )

    def index_text(
        self, context: TenantContext, *, document_id: str,
        expected_revision: int, title: str, content: str,
        source_kind: str = "text", source_ref: str | None = None,
    ) -> KnowledgeVersionResult:
        if (
            not isinstance(document_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", document_id)
            or type(expected_revision) is not int or expected_revision < 0
            or not isinstance(title, str) or not (1 <= len(title.strip()) <= 255)
            or not isinstance(content, str) or not content.strip()
            or len(content) > _MAX_CONTENT
            or len(context.credential_id) > 64
            or source_kind not in {"text", "file", "url"}
            or (source_kind == "text" and source_ref is not None)
            or (source_kind != "text" and (
                not isinstance(source_ref, str) or not 1 <= len(source_ref) <= 512
            ))
        ):
            raise KnowledgeVersionDenied("f4.index_invalid")
        title, content = title.strip(), content.strip()
        chunks = split_knowledge_chunks(content)
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not _SHA256.fullmatch(sha):
            raise KnowledgeVersionDenied("f4.hash_invalid")
        now = datetime.now(UTC)
        with self._sessions.begin() as db:
            doc = db.scalar(select(KnowledgeDocumentORM).where(
                KnowledgeDocumentORM.document_id == document_id,
                KnowledgeDocumentORM.tenant_id == context.tenant_id,
                KnowledgeDocumentORM.unit_id == context.unit_id,
                KnowledgeDocumentORM.active.is_(True),
            ).with_for_update())
            if doc is None:
                raise KnowledgeVersionDenied("f4.document_scope_denied")
            latest = db.scalar(select(KnowledgeSourceVersionORM).where(
                KnowledgeSourceVersionORM.document_id == document_id,
                KnowledgeSourceVersionORM.tenant_id == context.tenant_id,
                KnowledgeSourceVersionORM.unit_id == context.unit_id,
            ).order_by(KnowledgeSourceVersionORM.revision.desc()).limit(1))
            current_revision = latest.revision if latest else 0
            if expected_revision != current_revision:
                raise KnowledgeVersionDenied("f4.stale_revision")
            # An imported URL/file can only advance with its original provenance.
            # The legacy text endpoint must never relabel a governed source.
            if latest is not None and (
                latest.source_kind != source_kind or latest.source_ref != source_ref
            ):
                raise KnowledgeVersionDenied("f4.source_provenance_mismatch")
            if latest is None and source_kind != "text":
                raise KnowledgeVersionDenied("f4.source_missing")
            if latest is None and (
                title != doc.title or content != doc.content.strip()
            ):
                raise KnowledgeVersionDenied("f4.bootstrap_existing_first")
            if latest is not None and sha == latest.content_sha256 and title == latest.title:
                return KnowledgeVersionResult(
                    document_id=document_id, revision=latest.revision,
                    chunks=db.query(KnowledgeChunkORM).filter_by(
                        document_id=document_id, revision=latest.revision,
                    ).count(),
                    content_sha256=sha, indexed=False,
                )
            version = current_revision + 1
            if version > 2_000_000_000:
                raise KnowledgeVersionDenied("f4.revision_limit")
            db.add(KnowledgeSourceVersionORM(
                document_id=document_id, revision=version,
                tenant_id=context.tenant_id, unit_id=context.unit_id,
                title=title, content_sha256=sha, source_kind=source_kind,
                source_ref=source_ref, actor_credential_id=context.credential_id,
                created_at=now,
            ))
            for ordinal, (begin, end, chunk) in enumerate(chunks):
                db.add(KnowledgeChunkORM(
                    document_id=document_id, revision=version, ordinal=ordinal,
                    tenant_id=context.tenant_id, unit_id=context.unit_id,
                    start_offset=begin, end_offset=end, content=chunk,
                    content_sha256=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                    created_at=now,
                ))
            # Preserve the canonical existing document repository and its
            # current-state consumers; no parallel document authority.
            doc.title = title
            doc.content = content
            doc.updated_at = now
        return KnowledgeVersionResult(
            document_id=document_id, revision=version,
            chunks=len(chunks), content_sha256=sha, indexed=True,
        )
