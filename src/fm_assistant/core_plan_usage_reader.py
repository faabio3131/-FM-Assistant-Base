"""Safe, bounded Core metering read. Never infer zero from transport errors."""
from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from .plan_consumption_view import MeterReading


class CoreQuotaUsageHTTPReader:
    def __init__(self, *, core_origin: str, service_key: str) -> None:
        url = urlsplit(core_origin)
        if (
            url.scheme != "https" or not url.hostname or url.username
            or url.password or url.query or url.fragment
            or url.path not in {"", "/"} or not service_key
        ):
            raise ValueError("plan.core_transport_untrusted")
        self._origin = core_origin.rstrip("/")
        self._key = service_key

    def read(
        self, *, tenant_id: str, unit_id: str, metric: str,
        scope: str, at: datetime, policy_revision: int,
        limit_units: int, window_seconds: int,
    ) -> MeterReading | None:
        try:
            response = httpx.get(
                self._origin + "/v1/plan/usage",
                params={
                    "tenant_id": tenant_id, "unit_id": unit_id,
                    "resource": metric, "scope": scope,
                },
                headers={"X-Core-Service-Key": self._key},
                timeout=3.0, follow_redirects=False,
            )
            if response.status_code != 200 or len(response.content) > 4096:
                return None
            data = response.json()
            if not isinstance(data, dict) or any(
                data.get(name) != value for name, value in {
                    "tenant_id": tenant_id, "unit_id": unit_id,
                    "resource": metric, "scope": scope,
                    "policy_revision": policy_revision,
                    "limit_units": limit_units,
                    "window_seconds": window_seconds,
                }.items()
            ):
                return None
            for name in ("consumed_units", "reserved_units", "remaining_units"):
                value = data.get(name)
                if type(value) is not int or value < 0:
                    return None
            observed_at = datetime.fromisoformat(data["observed_at"])
            if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                return None
            elapsed = (at.astimezone(UTC) - observed_at.astimezone(UTC)).total_seconds()
            if not -15 <= elapsed <= 90:
                return None
            return MeterReading(
                consumed_units=data["consumed_units"],
                reserved_units=data["reserved_units"],
                remaining_units=data["remaining_units"],
                observed_at=observed_at,
                policy_revision=policy_revision,
                limit_units=limit_units, window_seconds=window_seconds,
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError, OverflowError):
            return None
