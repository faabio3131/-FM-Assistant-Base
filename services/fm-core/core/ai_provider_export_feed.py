"""F3 configurable read-only export feed for FM-approved report synchronisation.

Not a provider-invoice validator. Any imported observation still requires a
verified FM human JWT + service transport key via the existing Command gate.
No caller may supply a URL or an HTTP credential to this connector.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit

import httpx

from core.ai_control_plane import ControlPlaneError
from core.ai_provider_billing_export import ProviderExportPolicy, ProviderExportRecord

_SCHEMA = "fm.provider.export-read.v1"
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,249}[a-z0-9])?$")
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


@dataclass(frozen=True, kw_only=True)
class ProviderFeedConfig:
    provider: str
    account_ref: str
    adapter: str
    url: str
    host: str
    token: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all(
            type(x) is str and _ID.fullmatch(x)
            for x in (self.provider, self.account_ref)
        ) or self.adapter not in {"openai_compatible", "gemini"}:
            raise ControlPlaneError("core_finops.feed_policy_invalid")
        if type(self.url) is not str or len(self.url) > 1024:
            raise ControlPlaneError("core_finops.feed_url_invalid")
        try:
            parsed = urlsplit(self.url)
            hostname = parsed.hostname or ""
            port = parsed.port
        except ValueError as exc:
            raise ControlPlaneError("core_finops.feed_url_invalid") from exc
        if (
            parsed.scheme != "https" or parsed.username is not None
            or parsed.password is not None or port not in (None, 443)
            or not parsed.path.startswith("/") or parsed.path == "/"
            or parsed.query or parsed.fragment
            or hostname != self.host
            or not _HOST.fullmatch(hostname)
            or hostname.startswith("localhost")
            or hostname.endswith((".localhost", ".local", ".internal", ".test"))
        ):
            raise ControlPlaneError("core_finops.feed_url_invalid")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise ControlPlaneError("core_finops.feed_host_not_dns")
        if (
            type(self.token) is not str or len(self.token) < 32
            or any(c in self.token for c in "\r\n")
        ):
            raise ControlPlaneError("core_finops.feed_token_invalid")


def configured_feed(
    provider: str, account_ref: str, *,
    raw: str | None = None,
) -> ProviderFeedConfig:
    """Only FM-controlled process environment can select a source URL/key."""
    source = raw if raw is not None else os.environ.get(
        "FM_CORE_PROVIDER_EXPORT_FEEDS_JSON", ""
    )
    if not source or len(source) > 20_000:
        raise ControlPlaneError("core_finops.feed_not_configured")
    try:
        configurations = json.loads(source)
    except ValueError as exc:
        raise ControlPlaneError("core_finops.feed_configuration_invalid") from exc
    if not isinstance(configurations, list) or not 1 <= len(configurations) <= 16:
        raise ControlPlaneError("core_finops.feed_configuration_invalid")
    matches = []
    ids = set()
    for item in configurations:
        if not isinstance(item, dict) or set(item) != {
            "provider", "account_ref", "adapter", "url", "host", "token",
        }:
            raise ControlPlaneError("core_finops.feed_configuration_invalid")
        try:
            config = ProviderFeedConfig(**item)
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError("core_finops.feed_configuration_invalid") from exc
        key = (config.provider, config.account_ref)
        if key in ids:
            raise ControlPlaneError("core_finops.feed_duplicate_source")
        ids.add(key)
        if key == (provider, account_ref):
            matches.append(config)
    if len(matches) != 1:
        raise ControlPlaneError("core_finops.feed_not_configured")
    return matches[0]


def fetch_observations(
    *, config: ProviderFeedConfig, tenant_id: str, unit_id: str,
    attempts: list[dict[str, str]],
    transport: httpx.BaseTransport | None = None,
) -> tuple[ProviderExportPolicy, tuple[ProviderExportRecord, ...]]:
    """Fetch a report's physical-attempt observations without sending prompts.

    All returned records are checked against an exact requested attempt ID.
    Partial response is permitted (missing remains missing), but extra or
    conflicting records reject the entire proposed batch.
    """
    if (
        not all(type(v) is str and _ID.fullmatch(v) for v in (tenant_id, unit_id))
        or type(attempts) is not list or not 1 <= len(attempts) <= 50
        or any(
            type(row) is not dict or set(row) != {
                "request_id", "attempt_id", "model",
            } or not all(
                type(value) is str and 1 <= len(value) <= 200
                for value in row.values()
            )
            for row in attempts
        )
    ):
        raise ControlPlaneError("core_finops.feed_request_invalid")
    requested = {(item["request_id"], item["attempt_id"]): item["model"]
                 for item in attempts}
    if len(requested) != len(attempts):
        raise ControlPlaneError("core_finops.feed_duplicate_request")
    body = {
        "schema": _SCHEMA, "tenant_id": tenant_id, "unit_id": unit_id,
        "provider": config.provider, "account_ref": config.account_ref,
        "attempts": attempts,
    }
    try:
        with httpx.Client(
            transport=transport, timeout=httpx.Timeout(8.0, connect=3.0),
            follow_redirects=False, trust_env=False,
        ) as client:
            with client.stream(
                "POST", config.url, json=body,
                headers={
                    "Authorization": "Bearer " + config.token,
                    "Accept": "application/json",
                },
            ) as response:
                if response.status_code != 200:
                    raise ControlPlaneError("core_finops.feed_remote_unavailable")
                chunks: list[bytes] = []
                total = 0
                for part in response.iter_bytes():
                    total += len(part)
                    if total > 512 * 1024:
                        raise ControlPlaneError("core_finops.feed_response_too_large")
                    chunks.append(part)
            result = json.loads(b"".join(chunks))
    except (httpx.HTTPError, ValueError) as exc:
        raise ControlPlaneError("core_finops.feed_remote_unavailable") from exc
    if (
        not isinstance(result, dict)
        or set(result) != {"schema", "records"}
        or result["schema"] != _SCHEMA
        or not isinstance(result["records"], list)
        or len(result["records"]) > len(attempts)
    ):
        raise ControlPlaneError("core_finops.feed_response_invalid")
    observations: list[ProviderExportRecord] = []
    seen: set[tuple[str, str]] = set()
    for item in result["records"]:
        if not isinstance(item, dict) or set(item) != {
            "tenant_id", "unit_id", "provider", "account_ref", "request_id",
            "attempt_id", "model", "source_ref", "observed_at", "usage", "cost_usd",
        }:
            raise ControlPlaneError("core_finops.feed_record_invalid")
        if any(
            type(item[name]) is not str or not 1 <= len(item[name]) <= 200
            for name in (
                "tenant_id", "unit_id", "provider", "account_ref",
                "request_id", "attempt_id", "model", "source_ref",
            )
        ):
            raise ControlPlaneError("core_finops.feed_record_invalid")
        key = (item["request_id"], item["attempt_id"])
        if (
            key not in requested or key in seen
            or item["tenant_id"] != tenant_id or item["unit_id"] != unit_id
            or item["provider"] != config.provider
            or item["account_ref"] != config.account_ref
            or item["model"] != requested[key]
        ):
            raise ControlPlaneError("core_finops.feed_record_scope_invalid")
        seen.add(key)
        try:
            observed = datetime.fromisoformat(item["observed_at"])
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError("core_finops.feed_time_invalid") from exc
        if observed.tzinfo is None:
            raise ControlPlaneError("core_finops.feed_time_invalid")
        observations.append(ProviderExportRecord(
            provider=config.provider, account_ref=config.account_ref,
            tenant_id=tenant_id, unit_id=unit_id,
            request_id=key[0], attempt_id=key[1], model=item["model"],
            source_ref=item["source_ref"], observed_at=observed,
            usage=item["usage"], cost_usd=item["cost_usd"],
        ))
    policy = ProviderExportPolicy(
        provider=config.provider, adapter=config.adapter,
        account_ref=config.account_ref, max_age_seconds=31 * 86400,
    )
    return policy, tuple(observations)
