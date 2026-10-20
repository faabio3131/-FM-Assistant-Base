"""F3 governed audio runtime: exact provider metering, quotas and no-replay.

Synthetic provider, disposable SQLAlchemy DB and no provider credentials.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_control_plane import (
    AIControlPlaneStore, ControlPlaneBase, RouteDefinition,
)
from core.ai_control_plane_runtime import CoreControlPlaneAIRuntime
from core.ai_plan_usage_guard import PlanQuotaPolicy, PlanUsageGuard
from core.ai_providers import _int_or_none
from core.ai_quota_store import QuotaDenied, QuotaReservations
from core.ai_router import CapabilityIA
from core.seguranca.segredos import SecretValue


class CredentialReader:
    def __init__(self):
        self.calls = 0

    def resolve(self, *, tenant_id, credential_source, secret_reference):
        assert tenant_id == "tenant-a"
        assert credential_source == "fm_managed"
        self.calls += 1
        return SecretValue("synthetic-provider-token")


class LicensedAudio:
    def __init__(self, *, active=True):
        self.active = active

    def resolve(self, *, tenant_id, unit_id, capability, now):
        assert capability == CapabilityIA.ATENDIMENTO_TRANSCRICAO.value
        return PlanQuotaPolicy(
            tenant_id=tenant_id, unit_id=unit_id,
            plan_code="FULL_FUNCTIONS_CAPPED", revision=3,
            valid_until=now + timedelta(minutes=2) if self.active
            else now - timedelta(seconds=1),
            input_bound=64, output_bound=17,
            scopes=(("ai.requests", "tenant"),
                    ("ai.total_tokens", "tenant")),
            grants=(("ai.requests", "tenant", 2, 86400),
                    ("ai.total_tokens", "tenant", 200, 86400)),
        )


@pytest.fixture()
def audio_runtime():
    engine = create_engine("sqlite://")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    control = AIControlPlaneStore(sessions)
    control.register_provider(
        provider_id="gemini",
        adapter="gemini",
        base_url="https://provider.invalid/v1",
    )
    control.register_model(
        model_id="audio-model", provider_id="gemini", name="audio-test",
    )
    control.grant_capability(
        model_id="audio-model",
        capability=CapabilityIA.ATENDIMENTO_TRANSCRICAO,
    )
    control.set_provider_health(
        provider_id="gemini", status="healthy", circuit="closed",
    )
    primary = RouteDefinition(
        policy_id="audio-primary", scope="platform",
        tenant_id=None, unit_id=None, model_id="audio-model",
        capability=CapabilityIA.ATENDIMENTO_TRANSCRICAO,
        priority=100, price_snapshot_id="fm-audio-price",
        credential_source="fm_managed",
        secret_reference="env:FAKE_TEST_SECRET",
    )
    control.add_route(primary)
    ledger = QuotaReservations(sessions)
    creds = CredentialReader()
    def runtime(*, active=True, max_audio_bytes=10*1024*1024):
        return CoreControlPlaneAIRuntime(
            control_plane=control, credentials=creds,
            plan_usage=PlanUsageGuard(
                quota=ledger, authority=LicensedAudio(active=active),
                max_audio_bytes=max_audio_bytes,
            ),
        )
    yield control, ledger, creds, runtime, primary
    engine.dispose()


def transcribe(runtime, *, request_id="audio-1", audio=b"fake-wav"):
    return runtime.transcribe_audio(
        tenant_id="tenant-a",unit_id="unit-a",request_id=request_id,
        correlation_id=request_id,audio=audio,mime_type="audio/wav",
        instruction="Transcreva em pt-BR",
    )


def provider_json(*, prompt=10, output=5, cached=0):
    return {
        "candidates":[{"content":{"parts":[{"text":"audio transcrito"}]}}],
        "usageMetadata":{
            "promptTokenCount":prompt,"candidatesTokenCount":output,
            "cachedContentTokenCount":cached,
        },
    }


def fake_response(url, payload):
    return httpx.Response(
        200,json=payload,request=httpx.Request("POST",url),
    )


def test_audio_consumes_canonical_tokens_after_pre_admission(audio_runtime, monkeypatch):
    _, ledger, creds, runtime, _ = audio_runtime
    calls = []
    def post(url, **kw):
        calls.append(kw["json"]["generationConfig"]["maxOutputTokens"])
        assert "inlineData" in kw["json"]["contents"][0]["parts"][1]
        return fake_response(url,provider_json())
    monkeypatch.setattr("core.ai_providers.httpx.post",post)
    result = transcribe(runtime())
    assert result.content == "audio transcrito"
    assert calls == [17]
    assert creds.calls == 1
    usage = ledger.usage_snapshot(
        tenant_id="tenant-a",unit_id="__tenant__",capability="ai.total_tokens",
        at=datetime.now(UTC),
    )
    assert (usage.consumed_units,usage.reserved_units)==(15,0)
    with pytest.raises(QuotaDenied,match="execution_replay_denied"):
        transcribe(runtime())
    assert creds.calls == 1


def test_audio_unknown_provider_metering_cannot_be_falsely_refunded(
    audio_runtime,monkeypatch,
):
    _,ledger,_,runtime,_ = audio_runtime
    monkeypatch.setattr(
        "core.ai_providers.httpx.post",
        lambda url,**kw: fake_response(url,provider_json(prompt=1.5)),
    )
    assert transcribe(runtime()).content=="audio transcrito"
    snapshot=ledger.usage_snapshot(
        tenant_id="tenant-a",unit_id="__tenant__",capability="ai.total_tokens",
        at=datetime.now(UTC),
    )
    assert (snapshot.consumed_units,snapshot.reserved_units)==(0,81)
    with pytest.raises(QuotaDenied,match="execution_replay_denied"):
        transcribe(runtime())


def test_audio_oversize_and_revoked_license_never_resolve_secret(
    audio_runtime,monkeypatch,
):
    _,ledger,creds,runtime,_ = audio_runtime
    sends = []
    monkeypatch.setattr("core.ai_providers.httpx.post",lambda *a,**kw:sends.append(a))
    with pytest.raises(QuotaDenied,match="audio_upload_exceeded"):
        transcribe(runtime(max_audio_bytes=4),request_id="oversized",audio=b"012345")
    with pytest.raises(QuotaDenied,match="license_unavailable"):
        transcribe(runtime(active=False),request_id="revoked")
    assert creds.calls==0 and sends==[]
    with ledger._sessions() as db:
        from sqlalchemy import select
        from core.ai_quota_store import AIQuotaReservationRecord
        assert db.scalars(select(AIQuotaReservationRecord)).all() == []


def test_audio_fallback_budget_retained_after_uncertain_first_attempt(
    audio_runtime,monkeypatch,
):
    control,ledger,creds,runtime,primary=audio_runtime
    control.add_route(replace(
        primary,policy_id="audio-fallback",priority=90,
        price_snapshot_id="fm-audio-fallback",
    ))
    count=0
    def post(url,**kwargs):
        nonlocal count
        count+=1
        assert kwargs["json"]["generationConfig"]["maxOutputTokens"]==17
        if count==1:
            return httpx.Response(503,request=httpx.Request("POST",url))
        return fake_response(url,provider_json())
    monkeypatch.setattr("core.ai_providers.httpx.post",post)
    assert transcribe(runtime()).content=="audio transcrito"
    assert count==2 and creds.calls==2
    usage=ledger.usage_snapshot(
        tenant_id="tenant-a",unit_id="__tenant__",capability="ai.total_tokens",
        at=datetime.now(UTC),
    )
    assert (usage.consumed_units,usage.reserved_units)==(0,162)


@pytest.mark.parametrize("invalid",[True,False,-1,1.2,float("nan"),"1.5"," 7","7 ",
                                      "1e4","NaN","-2","99999999999",[],{}])
def test_exact_provider_usage_avoids_boolean_fraction_overflow_coercion(invalid):
    assert _int_or_none(invalid) is None


@pytest.mark.parametrize(("value","expected"),[(0,0),(4,4),("004",4),("12",12),
                                                 (2_000_000_000,2_000_000_000)])
def test_provider_usage_accepts_only_exact_nonnegative_counts(value,expected):
    assert _int_or_none(value)==expected
