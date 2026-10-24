"""Deterministic F4 data minimization at every assistant-context boundary.

Never modify the source-of-truth documents or their version hashes; only the
read-side evidence is sanitized. Unknown sensitive patterns remain a residual
risk and should be addressed by human approval of customer-managed sources.
"""
from __future__ import annotations

import re

_MASK = "[DADO_RESTRITO]"
_PATTERNS = (
    # Token-shaped credentials, independent of any associated field name.
    re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|nvapi-[A-Za-z0-9_-]{12,}|"
               r"gh[pousr]_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,})"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|"
               r"secret|senha|password|client[_ -]?secret)\s*[:=]\s*"
               r"[\"']?[^\s\"',;]{4,}"),
    re.compile(r"(?i)(?<![\w.+-])[A-Za-z0-9._%+-]{1,64}@"
               r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?![\w.-])"),
    re.compile(r"(?<!\d)\d{3}[.]?\d{3}[.]?\d{3}[-]?\d{2}(?!\d)"),
    re.compile(r"(?<!\w)\+55\s*\(?\d{2}\)?[\s-]*\d{4,5}[\s-]*\d{4}(?!\w)"),
)


def redact_knowledge_evidence(value: str) -> str:
    """Mask obvious identifiers and secrets without changing stored provenance."""
    if not isinstance(value, str):
        return ""
    for pattern in _PATTERNS:
        value = pattern.sub(_MASK, value)
    return value
