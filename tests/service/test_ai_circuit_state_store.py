"""F3.8 persistent circuit guards on a disposable SQLAlchemy database."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.ai_circuit_breaker import CircuitDenied, CircuitOutcome, CircuitPolicy
from core.ai_circuit_state_store import PersistentCircuit, ProviderCircuitRecord
from core.ai_control_plane import AIProvider, ControlPlaneBase

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)
POLICY = CircuitPolicy(threshold=2, cooldown_seconds=30, probe_seconds=5)


@pytest.fixture
def circuit(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'circuit.db'}")
    ControlPlaneBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(AIProvider(
            provider_id="provider-a", adapter="gemini",
            base_url="https://invalid.example", enabled=True,
        ))
        db.add(ProviderCircuitRecord(
            provider_id="provider-a", phase="closed", failures=0,
            until=None, probe_id=None, version=1,
        ))
    yield PersistentCircuit(sessions, POLICY)
    engine.dispose()


def test_open_claim_single_probe_success_and_fencing(circuit):
    _, v = circuit.claim(provider_id="provider-a", now=NOW)
    circuit.finish(
        provider_id="provider-a", now=NOW,
        outcome=CircuitOutcome.TRANSIENT_FAILURE, probe_id=None, version=v,
    )
    _, v = circuit.claim(provider_id="provider-a", now=NOW)
    circuit.finish(
        provider_id="provider-a", now=NOW,
        outcome=CircuitOutcome.TRANSIENT_FAILURE, probe_id=None, version=v,
    )
    with pytest.raises(CircuitDenied, match="circuit.open"):
        circuit.claim(provider_id="provider-a", now=NOW)
    token, fence = circuit.claim(
        provider_id="provider-a", now=NOW + timedelta(seconds=30),
    )
    assert token and fence > 1
    with pytest.raises(CircuitDenied, match="probe_busy"):
        circuit.claim(provider_id="provider-a", now=NOW + timedelta(seconds=31))
    with pytest.raises(CircuitDenied, match="stale_fence"):
        circuit.finish(
            provider_id="provider-a", now=NOW + timedelta(seconds=31),
            outcome=CircuitOutcome.SUCCESS, probe_id=token, version=fence - 1,
        )
    circuit.finish(
        provider_id="provider-a", now=NOW + timedelta(seconds=31),
        outcome=CircuitOutcome.SUCCESS, probe_id=token, version=fence,
    )
    assert circuit.claim(provider_id="provider-a", now=NOW)[0] is None


def test_expired_probe_reopens_then_rejects_old_result(circuit):
    for i in range(2):
        _, fence = circuit.claim(provider_id="provider-a", now=NOW)
        circuit.finish(
            provider_id="provider-a", now=NOW,
            outcome=CircuitOutcome.TRANSIENT_FAILURE,
            probe_id=None, version=fence,
        )
    token, fence = circuit.claim(
        provider_id="provider-a", now=NOW + timedelta(seconds=30),
    )
    circuit.recover_expired(
        provider_id="provider-a", now=NOW + timedelta(seconds=36),
    )
    with pytest.raises(CircuitDenied):
        circuit.finish(
            provider_id="provider-a", now=NOW + timedelta(seconds=36),
            outcome=CircuitOutcome.SUCCESS, probe_id=token, version=fence,
        )
    with pytest.raises(CircuitDenied, match="circuit.open"):
        circuit.claim(provider_id="provider-a", now=NOW + timedelta(seconds=37))


def test_missing_circuit_configuration_denies(circuit):
    with pytest.raises(CircuitDenied, match="circuit.unconfigured"):
        circuit.claim(provider_id="unknown", now=NOW)


def test_unaware_time_denied_before_mutation(circuit):
    with pytest.raises(CircuitDenied, match="circuit.invalid_time"):
        circuit.claim(provider_id="provider-a", now=datetime(2026, 10, 18))
