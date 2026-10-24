"""Governed F4 source ports. Import is off until FM enables it.

Never trust client-supplied tenant/unit, filename, URL, response content type,
or external text as instructions. Only plaintext snapshots enter the knowledge
index; remote media is never executed or stored as HTML.
"""
from __future__ import annotations

import http.client
import ipaddress
import os
import re
import socket
import ssl
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlsplit

from sqlalchemy import select

from .db import KnowledgeDocumentORM, KnowledgeSourceVersionORM
from .domain import TenantContext
from .knowledge_versioning import KnowledgeVersionResult, VersionedKnowledgeIngestion

_MAX_UPLOAD = 1_500_000
_MAX_TEXT = 24_000
_HOST = re.compile(r"^[a-z0-9-]{1,63}(?:\\.[a-z0-9-]{1,63})+$")
_TYPES = {
    ".txt": ("text/plain",),
    ".md": ("text/markdown", "text/plain"),
    ".csv": ("text/csv", "text/plain", "application/csv"),
    ".html": ("text/html",),
    ".htm": ("text/html",),
    ".pdf": ("application/pdf",),
}


class SourceImportDenied(ValueError):
    pass


class _PlainHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocks: list[str] = []
        self._blocked = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "template", "noscript", "svg"}:
            self._blocked += 1
        if tag in {"p", "li", "br", "div", "h1", "h2", "h3", "tr"}:
            self._blocks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript", "svg"}:
            self._blocked = max(0, self._blocked - 1)

    def handle_data(self, data: str) -> None:
        if not self._blocked:
            self._blocks.append(data)

    def result(self) -> str:
        return " ".join("".join(self._blocks).split())


def _decode(data: bytes, suffix: str) -> str:
    if not data or len(data) > _MAX_UPLOAD:
        raise SourceImportDenied("f4.file_size_invalid")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            pdf = PdfReader(BytesIO(data), strict=True)
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 30:
                raise SourceImportDenied("f4.pdf_invalid")
            extracted = []
            chars = 0
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                chars += len(page_text)
                if chars > _MAX_TEXT:
                    raise SourceImportDenied("f4.extracted_content_limit")
                extracted.append(page_text)
            text = "\n".join(extracted)
        except SourceImportDenied:
            raise
        except Exception as exc:
            raise SourceImportDenied("f4.pdf_invalid") from exc
    else:
        try:
            text = data.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise SourceImportDenied("f4.file_encoding_invalid") from exc
        if "\x00" in text:
            raise SourceImportDenied("f4.binary_not_allowed")
        if suffix in {".html", ".htm"}:
            parser = _PlainHTML()
            parser.feed(text)
            text = parser.result()
    text = text.strip()
    if not text or len(text) > _MAX_TEXT:
        raise SourceImportDenied("f4.extracted_content_limit")
    return text


def _checked_host(url: str, hosts: frozenset[str], resolver) -> tuple[str, tuple[str, ...]]:
    if not isinstance(url, str) or len(url) > 512 or not hosts:
        raise SourceImportDenied("f4.url_disabled")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.port not in (None, 443)
                or not _HOST.fullmatch(host) or host not in hosts
                or parsed.netloc != host and parsed.netloc != host + ":443"
                or not (parsed.path == "" or parsed.path.startswith("/"))):
            raise SourceImportDenied("f4.url_denied")
        addresses = resolver(host, 443)
        if not addresses or len(addresses) > 16:
            raise SourceImportDenied("f4.url_dns_denied")
        if any(not ipaddress.ip_address(str(ip)).is_global for ip in addresses):
            raise SourceImportDenied("f4.url_dns_denied")
        return host, tuple(str(ip) for ip in addresses)
    except SourceImportDenied:
        raise
    except (ValueError, OSError) as exc:
        raise SourceImportDenied("f4.url_denied") from exc


def _resolve_public(host: str, port: int) -> list[str]:
    return sorted({address[4][0] for address in socket.getaddrinfo(
        host, port, type=socket.SOCK_STREAM,
    )})


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TLS hostname verified, TCP peer pinned to one prevalidated public IP."""

    def __init__(self, hostname: str, ip: str) -> None:
        super().__init__(hostname, port=443, timeout=5, context=ssl.create_default_context())
        self._pinned_ip = ip

    def connect(self) -> None:
        raw = socket.create_connection((self._pinned_ip, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _fetch_https(url: str, addresses: tuple[str, ...]) -> tuple[bytes, str]:
    # Reuse exactly the DNS addresses validated by _checked_host. Never perform
    # a second DNS lookup after approval: rebinding would defeat SSRF checks.
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    request_path = parts.path or "/"
    for address in addresses:
        conn = _PinnedHTTPSConnection(hostname, address)
        try:
            conn.request("GET", request_path, headers={
                "Accept": "text/plain,text/markdown,text/csv,text/html,application/pdf",
                "Accept-Encoding": "identity",
                "User-Agent": "VendeAtendeIA-Knowledge/1.0",
                "Connection": "close",
            })
            response = conn.getresponse()
            if response.status != 200:
                raise SourceImportDenied("f4.url_response_denied")
            if response.getheader("content-encoding", "identity").lower() != "identity":
                raise SourceImportDenied("f4.url_encoding_denied")
            content_type = response.getheader("content-type", "").split(";")[0].lower().strip()
            length = response.getheader("content-length")
            if length is not None and (not length.isdecimal() or int(length) > _MAX_UPLOAD):
                raise SourceImportDenied("f4.url_too_large")
            body = response.read(_MAX_UPLOAD + 1)
            if len(body) > _MAX_UPLOAD:
                raise SourceImportDenied("f4.url_too_large")
            return body, content_type
        except SourceImportDenied:
            raise
        except (OSError, ssl.SSLError, http.client.HTTPException, ValueError):
            # Another approved address may succeed; no alternate host, proxy
            # or private IP fallback is ever used.
            continue
        finally:
            conn.close()
    raise SourceImportDenied("f4.url_unavailable")


@dataclass(frozen=True)
class SourceImportResult:
    document_id: str
    revision: int
    chunks: int
    content_sha256: str
    source_kind: str
    external_source_verified: bool = False


class GovernedKnowledgeSources:
    def __init__(self, sessions, *, fetcher=None, resolver=None) -> None:
        self._sessions = sessions
        self._versioning = VersionedKnowledgeIngestion(sessions)
        self._fetcher = fetcher or _fetch_https
        self._resolver = resolver or _resolve_public

    def import_file(
        self, context: TenantContext, *, filename: str,
        media_type: str, content: bytes, title: str,
    ) -> SourceImportResult:
        if (not isinstance(filename, str) or not 1 <= len(filename) <= 160
                or not filename.isprintable() or filename in (".", "..")
                or any(char in filename for char in ("/", "\\", ":", "\x00"))):
            raise SourceImportDenied("f4.filename_invalid")
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
        if (suffix not in _TYPES or media_type not in _TYPES[suffix]):
            raise SourceImportDenied("f4.file_type_denied")
        text = _decode(content, suffix)
        return self._store(context, title=title, content=text, kind="file",
                           ref=filename)

    def import_url(self, context: TenantContext, *, url: str, title: str) -> SourceImportResult:
        configured = os.environ.get("FM_ASSISTANT_KNOWLEDGE_URL_ALLOWED_HOSTS", "")
        hosts = frozenset(h.strip().lower() for h in configured.split(",") if h.strip())
        if not all(_HOST.fullmatch(h) for h in hosts):
            raise SourceImportDenied("f4.url_allowlist_invalid")
        _, addresses = _checked_host(url, hosts, self._resolver)
        data, content_type = self._fetcher(url, addresses)
        ext = {
            "text/plain": ".txt", "text/markdown": ".md",
            "text/html": ".html", "text/csv": ".csv",
            "application/pdf": ".pdf",
        }.get(content_type)
        if not ext:
            raise SourceImportDenied("f4.url_type_denied")
        text = _decode(data, ext)
        return self._store(context, title=title, content=text, kind="url", ref=url)

    def _store(
        self, context: TenantContext, *, title: str, content: str,
        kind: str, ref: str,
    ) -> SourceImportResult:
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 255:
            raise SourceImportDenied("f4.title_invalid")
        if not context.tenant_id or not context.unit_id:
            raise SourceImportDenied("f4.scope_invalid")
        result: KnowledgeVersionResult = self._versioning.create_source(
            context, title=title.strip(), content=content, source_kind=kind,
            source_ref=ref,
        )
        return SourceImportResult(
            document_id=result.document_id, revision=result.revision,
            chunks=result.chunks, content_sha256=result.content_sha256,
            source_kind=kind,
        )

    def list_sources(self, context: TenantContext, *, page: int = 0) -> dict:
        if type(page) is not int or not 0 <= page <= 200:
            raise SourceImportDenied("f4.page_invalid")
        with self._sessions() as db:
            rows = db.scalars(select(KnowledgeDocumentORM).where(
                KnowledgeDocumentORM.tenant_id == context.tenant_id,
                KnowledgeDocumentORM.unit_id == context.unit_id,
            ).order_by(KnowledgeDocumentORM.updated_at.desc(),
                       KnowledgeDocumentORM.document_id.asc())
                              .offset(page * 50).limit(51)).all()
            items = []
            for doc in rows[:50]:
                version = db.scalar(select(KnowledgeSourceVersionORM).where(
                    KnowledgeSourceVersionORM.tenant_id == context.tenant_id,
                    KnowledgeSourceVersionORM.unit_id == context.unit_id,
                    KnowledgeSourceVersionORM.document_id == doc.document_id,
                ).order_by(KnowledgeSourceVersionORM.revision.desc()).limit(1))
                items.append({
                    "document_id": doc.document_id, "title": doc.title,
                    "active": doc.active, "updated_at": doc.updated_at.isoformat(),
                    "revision": version.revision if version else None,
                    "source_kind": version.source_kind if version else "text",
                    "source_ref": version.source_ref if version else None,
                    "content_sha256": version.content_sha256 if version else None,
                    "external_source_verified": False,
                })
            return {"items": items, "page": page,
                    "next_page": page + 1 if len(rows) > 50 else None}
