"""F3.8 fail-closed deterministic circuit tests; no real provider calls."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.ai_circuit_breaker import (
    CircuitDenied,
    CircuitOutcome,
    CircuitPhase,
    CircuitPolicy,
    CircuitState,
    admit,
    expire_probe,
    settle,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
POLICY = CircuitPolicy(threshold=2, cooldown_seconds=30, probe_seconds=5)


def test_closed_to_open_exact_threshold_and_cooldown():
    state, lease = admit(CircuitState(), POLICY, now=NOW)
    assert lease is None
    first = settle(state, POLICY, now=NOW, outcome=CircuitOutcome.TRANSIENT_FAILURE)
    assert first.phase is CircuitPhase.CLOSED
    assert first.failures == 1
    second = settle(first, POLICY, now=NOW, outcome=CircuitOutcome.TRANSIENT_FAILURE)
    assert second.phase is CircuitPhase.OPEN
    assert second.until == NOW + timedelta(seconds=30)
    with pytest.raises(CircuitDenied, match="circuit.open"):
        admit(second, POLICY, now=NOW + timedelta(seconds=29), probe_id="worker-a")


def test_half_open_allows_one_probe_and_recovery():
    opened = settle(
        settle(CircuitState(), POLICY, now=NOW, outcome=CircuitOutcome.TRANSIENT_FAILURE),
        POLICY, now=NOW, outcome=CircuitOutcome.TRANSIENT_FAILURE,
    )
    half, token = admit(opened, POLICY, now=NOW + timedelta(seconds=30), probe_id="lease-1")
    assert token == "lease-1"
    assert half.phase is CircuitPhase.HALF_OPEN
    with pytest.raises(CircuitDenied, match="probe_busy"):
        admit(half, POLICY, now=NOW + timedelta(seconds=31), probe_id="lease-2")
    with pytest.raises(CircuitDenied, match="stale_probe"):
        settle(
            half, POLICY, now=NOW + timedelta(seconds=31),
            outcome=CircuitOutcome.SUCCESS, probe_id="spoofed",
        )
    assert settle(
        half, POLICY, now=NOW + timedelta(seconds=31),
        outcome=CircuitOutcome.SUCCESS, probe_id=token,
    ) == CircuitState()


@pytest.mark.parametrize("outcome", [
    CircuitOutcome.TRANSIENT_FAILURE, CircuitOutcome.DEFINITIVE_FAILURE,
])
def test_failed_or_inconclusive_probe_reopens(outcome):
    opened = CircuitState(phase=CircuitPhase.OPEN, failures=2, until=NOW)
    half, token = admit(opened, POLICY, now=NOW, probe_id="claim")
    failed = settle(half, POLICY, now=NOW, outcome=outcome, probe_id=token)
    assert failed.phase is CircuitPhase.OPEN
    assert failed.until == NOW + timedelta(seconds=30)


def test_expired_lease_and_stale_result_are_denied():
    half, token = admit(
        CircuitState(phase=CircuitPhase.OPEN, failures=2, until=NOW),
        POLICY, now=NOW, probe_id="claim",
    )
    with pytest.raises(CircuitDenied, match="stale_probe"):
        settle(
            half, POLICY, now=NOW + timedelta(seconds=5),
            outcome=CircuitOutcome.SUCCESS, probe_id=token,
        )
    with pytest.raises(CircuitDenied, match="probe_busy"):
        admit(half, POLICY, now=NOW + timedelta(seconds=6), probe_id="another")


def test_permanent_client_error_does_not_open_provider_circuit():
    first = settle(
        CircuitState(), POLICY, now=NOW, outcome=CircuitOutcome.TRANSIENT_FAILURE,
    )
    second = settle(
        first, POLICY, now=NOW, outcome=CircuitOutcome.DEFINITIVE_FAILURE,
    )
    assert second == first
    assert settle(
        second, POLICY, now=NOW, outcome=CircuitOutcome.SUCCESS,
    ) == CircuitState()


@pytest.mark.parametrize("policy", [
    (0, 30, 5), (2, 0, 5), (2, 30, 0), (True, 30, 5), (2, -1, 5),
])
def test_invalid_policies_fail_closed(policy):
    with pytest.raises(CircuitDenied, match="invalid_policy"):
        CircuitPolicy(*policy)


def test_naive_time_is_denied_and_probe_token_required():
    opened = CircuitState(phase=CircuitPhase.OPEN, failures=2, until=NOW)
    with pytest.raises(CircuitDenied, match="invalid_time"):
        admit(opened, POLICY, now=datetime(2026, 10, 18))
    with pytest.raises(CircuitDenied, match="probe_required"):
        admit(opened, POLICY, now=NOW)


def test_open_state_cannot_be_settled_and_state_must_be_consistent():
    with pytest.raises(CircuitDenied, match="invalid_outcome"):
        settle(
            CircuitState(phase=CircuitPhase.OPEN, failures=2, until=NOW),
            POLICY, now=NOW, outcome=CircuitOutcome.SUCCESS,
        )
    with pytest.raises(CircuitDenied, match="invalid_state"):
        CircuitState(phase=CircuitPhase.HALF_OPEN, failures=2, until=NOW)


def test_expired_half_open_lease_reopens_with_new_cooldown():
    opened = CircuitState(phase=CircuitPhase.OPEN, failures=2, until=NOW)
    half, token = admit(opened, POLICY, now=NOW, probe_id="old-probe")
    with pytest.raises(CircuitDenied, match="probe_active"):
        expire_probe(half, POLICY, now=NOW + timedelta(seconds=4))
    recovered = expire_probe(half, POLICY, now=NOW + timedelta(seconds=5))
    assert recovered.phase is CircuitPhase.OPEN
    assert recovered.until == NOW + timedelta(seconds=35)
    with pytest.raises(CircuitDenied, match="open"):
        admit(recovered, POLICY, now=NOW + timedelta(seconds=6), probe_id="new")
    with pytest.raises(CircuitDenied, match="invalid_outcome"):
        settle(recovered, POLICY, now=NOW + timedelta(seconds=6),
               outcome=CircuitOutcome.SUCCESS, probe_id=token)
