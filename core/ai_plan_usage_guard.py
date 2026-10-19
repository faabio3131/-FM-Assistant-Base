"""Consumption-only FM plan guard; no feature gating and no provider secrets.

A trusted Assistant policy port supplies scoped, revisioned plan entitlements.
Every limit is reserved in one transaction before provider work; unknown
tokens retain the reservation rather than being accounted as zero.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from core.ai_quota_store import QuotaDenied, QuotaRequirement, QuotaReservations
from core.ai_router import AIUsageEvent, ConteudoAudioIA, SolicitacaoIA
from core.ai_service_contracts import TextRequestContent


@dataclass(frozen=True, kw_only=True)
class PlanQuotaPolicy:
    tenant_id: str
    unit_id: str
    plan_code: str
    revision: int
    valid_until: datetime
    input_bound: int
    output_bound: int
    # These are independently enforced metrics; ai.requests and
    # ai.total_tokens are always mandatory.
    scopes: tuple[tuple[str, str], ...]
    grants: tuple[tuple[str, str, int, int], ...] = ()
    attempt_budget: int = 1

    def __post_init__(self) -> None:
        if (
            not self.tenant_id or not self.unit_id or not self.plan_code
            or type(self.revision) is not int or self.revision < 1
            or type(self.attempt_budget) is not int
            or not 1 <= self.attempt_budget <= 8
            or (self.input_bound + self.output_bound) * self.attempt_budget > 2_000_000_000
            or self.valid_until.tzinfo is None
            or self.valid_until.utcoffset() is None
            or type(self.input_bound) is not int or self.input_bound <= 0
            or type(self.output_bound) is not int or self.output_bound <= 0
            or self.input_bound + self.output_bound > 2_000_000_000
        ):
            raise QuotaDenied("core_plan.policy_invalid")
        metrics = dict(self.scopes)
        if len(metrics) != len(self.scopes) or not {
            "ai.requests", "ai.total_tokens"
        }.issubset(metrics):
            raise QuotaDenied("core_plan.metrics_incomplete")
        if any(
            key not in {"ai.requests", "ai.total_tokens",
                        "ai.input_tokens", "ai.output_tokens", "ai.cached_tokens"}
            or scope not in {"tenant", "unit"}
            for key, scope in self.scopes
        ):
            raise QuotaDenied("core_plan.metric_scope_invalid")
        if self.grants and (
            len(self.grants) != len(self.scopes)
            or tuple((m, scope) for m, scope, _, _ in self.grants) != self.scopes
            or any(type(limit) is not int or not 0 < limit <= 2_000_000_000
                   or type(window) is not int or not 0 < window <= 31_536_000
                   for _, _, limit, window in self.grants)
        ):
            raise QuotaDenied("core_plan.grants_invalid")


class PlanPolicyAuthority(Protocol):
    def resolve(
        self, *, tenant_id: str, unit_id: str, capability: str,
        now: datetime,
    ) -> PlanQuotaPolicy: ...


class PlanUsageGuard:
    def __init__(
        self, *, quota: QuotaReservations, authority: PlanPolicyAuthority,
        max_audio_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        if type(max_audio_bytes) is not int or not 1 <= max_audio_bytes <= 64 * 1024 * 1024:
            raise ValueError("core_plan.audio_upload_ceiling_invalid")
        self._max_audio_bytes = max_audio_bytes
        self._quota = quota
        self._authority = authority

    def _policy(self, request: SolicitacaoIA, now: datetime) -> PlanQuotaPolicy:
        policy = self._authority.resolve(
            tenant_id=request.tenant_id, unit_id=request.unidade_id,
            capability=request.capability.value, now=now,
        )
        if (
            policy.tenant_id != request.tenant_id
            or policy.unit_id != request.unidade_id
            or policy.valid_until.astimezone(UTC) <= now
        ):
            raise QuotaDenied("core_plan.license_unavailable")
        return policy

    @staticmethod
    def _requirements(
        request: SolicitacaoIA, policy: PlanQuotaPolicy, *,
        usage: tuple[int, int, int] | None,
    ) -> tuple[QuotaRequirement, ...]:
        if usage is None:
            amounts = {
                "ai.requests": 1,
                "ai.total_tokens": (policy.input_bound + policy.output_bound)
                * policy.attempt_budget,
                "ai.input_tokens": policy.input_bound * policy.attempt_budget,
                "ai.output_tokens": policy.output_bound * policy.attempt_budget,
                # Cached tokens are a subset of input and must not add
                # themselves to total_tokens again.
                "ai.cached_tokens": policy.input_bound * policy.attempt_budget,
            }
        else:
            input_used, output_used, cached_used = usage
            if any(
                type(v) is not int or v < 0
                for v in (input_used, output_used, cached_used)
            ) or cached_used > input_used:
                raise QuotaDenied("core_plan.usage_invalid")
            amounts = {
                "ai.requests": 1,
                "ai.total_tokens": input_used + output_used,
                "ai.input_tokens": input_used,
                "ai.output_tokens": output_used,
                "ai.cached_tokens": cached_used,
            }
        return tuple(QuotaRequirement(
            tenant_id=request.tenant_id,
            unit_id="__tenant__" if scope == "tenant" else request.unidade_id,
            capability=metric,
            units=amounts[metric], policy_revision=policy.revision,
        ) for metric, scope in policy.scopes)

    def admit(
        self, *, request: SolicitacaoIA, at: datetime,
        attempt_budget: int = 1,
    ) -> PlanQuotaPolicy:
        now = at.astimezone(UTC)
        policy = replace(
            self._policy(request, now), attempt_budget=attempt_budget,
        )
        if isinstance(request.conteudo, TextRequestContent):
            # Conservative UTF-8 envelope. Provider tokenization is checked
            # separately; this rejects definitely oversized customer text
            # before any reservation or credentials are touched.
            content = request.conteudo
            byte_count = len(content.system_prompt.encode("utf-8"))
            byte_count += sum(
                len(msg.role.encode("utf-8")) + len(msg.content.encode("utf-8"))
                for msg in content.messages
            )
            if byte_count > policy.input_bound:
                raise QuotaDenied("core_plan.input_envelope_exceeded")
        if isinstance(request.conteudo, ConteudoAudioIA):
            # Transport-size containment, NOT a statement about audio token
            # equivalence. Actual model tokens remain separately metered.
            if len(request.conteudo.audio) > self._max_audio_bytes:
                raise QuotaDenied("core_plan.audio_upload_exceeded")
        if policy.grants:
            self._quota.project_signed_grants(
                tenant_id=request.tenant_id, unit_id=request.unidade_id,
                revision=policy.revision, grants=policy.grants,
            )
        self._quota.reserve_bundle(
            needs=self._requirements(request, policy, usage=None),
            request_id=request.request_id, at=now,
        )
        return policy

    def reconcile(
        self, *, request: SolicitacaoIA, policy: PlanQuotaPolicy,
        events: tuple[AIUsageEvent, ...],
    ) -> bool:
        """Return False when any attempt is unmetered; never refund unknowns."""
        if not events or any(
            event.tenant_id != request.tenant_id
            or event.unidade_id != request.unidade_id
            or event.request_id != request.request_id
            or event.input_tokens is None
            or event.output_tokens is None
            or event.cached_tokens is None
            or any(
                type(v) is not int or v < 0
                for v in (event.input_tokens, event.output_tokens, event.cached_tokens)
            )
            or event.cached_tokens > event.input_tokens
            for event in events
        ):
            return False
        used_input = sum(int(e.input_tokens) for e in events)
        used_output = sum(int(e.output_tokens) for e in events)
        used_cached = sum(int(e.cached_tokens) for e in events)
        if (
            len(events) > policy.attempt_budget
            or used_input > policy.input_bound * policy.attempt_budget
            or used_output > policy.output_bound * policy.attempt_budget
            or used_cached > used_input
        ):
            # Provider exceeded trusted caps; quarantine held reservation,
            # record discrepancy for operator review, never settle a lie.
            raise QuotaDenied("core_plan.actual_usage_exceeds_reserved")
        self._quota.settle_bundle(
            usage=self._requirements(
                request, policy, usage=(used_input, used_output, used_cached),
            ),
            request_id=request.request_id,
        )
        return True
