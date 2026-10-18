"""Pure F3.8 circuit transitions, without changing live routing.

A shared transactional store and fencing are mandatory before runtime use.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class CircuitDenied(ValueError):
    pass


class CircuitPhase(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOutcome(StrEnum):
    SUCCESS = "success"
    TRANSIENT_FAILURE = "transient_failure"
    DEFINITIVE_FAILURE = "definitive_failure"


@dataclass(frozen=True)
class CircuitPolicy:
    threshold: int
    cooldown_seconds: int
    probe_seconds: int

    def __post_init__(self) -> None:
        if any(type(v) is not int or not 1 <= v <= 86_400 for v in (
            self.threshold, self.cooldown_seconds, self.probe_seconds,
        )):
            raise CircuitDenied("circuit.invalid_policy")


@dataclass(frozen=True)
class CircuitState:
    phase: CircuitPhase = CircuitPhase.CLOSED
    failures: int = 0
    until: datetime | None = None
    probe_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.failures) is not int or self.failures < 0:
            raise CircuitDenied("circuit.invalid_state")
        if self.phase is CircuitPhase.CLOSED and (self.until or self.probe_id):
            raise CircuitDenied("circuit.invalid_state")
        if self.phase is CircuitPhase.OPEN and (not self.until or self.probe_id):
            raise CircuitDenied("circuit.invalid_state")
        if self.phase is CircuitPhase.HALF_OPEN and (not self.until or not self.probe_id):
            raise CircuitDenied("circuit.invalid_state")
        if self.until is not None:
            aware(self.until)


def aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CircuitDenied("circuit.invalid_time")
    return value.astimezone(UTC)


def admit(
    state: CircuitState, policy: CircuitPolicy, *, now: datetime,
    probe_id: str | None = None,
) -> tuple[CircuitState, str | None]:
    now = aware(now)
    if state.phase is CircuitPhase.CLOSED:
        if probe_id is not None:
            raise CircuitDenied("circuit.unexpected_probe")
        return state, None
    if state.phase is CircuitPhase.HALF_OPEN:
        raise CircuitDenied("circuit.probe_busy")
    if now < aware(state.until):
        raise CircuitDenied("circuit.open")
    if not isinstance(probe_id, str) or not 1 <= len(probe_id) <= 128:
        raise CircuitDenied("circuit.probe_required")
    return CircuitState(
        phase=CircuitPhase.HALF_OPEN,
        failures=state.failures,
        until=now + timedelta(seconds=policy.probe_seconds),
        probe_id=probe_id,
    ), probe_id


def settle(
    state: CircuitState, policy: CircuitPolicy, *, now: datetime,
    outcome: CircuitOutcome, probe_id: str | None = None,
) -> CircuitState:
    now = aware(now)
    if not isinstance(outcome, CircuitOutcome) or state.phase is CircuitPhase.OPEN:
        raise CircuitDenied("circuit.invalid_outcome")
    if state.phase is CircuitPhase.HALF_OPEN:
        if probe_id != state.probe_id or now >= aware(state.until):
            raise CircuitDenied("circuit.stale_probe")
        if outcome is CircuitOutcome.SUCCESS:
            return CircuitState()
        return CircuitState(
            phase=CircuitPhase.OPEN,
            failures=max(state.failures, policy.threshold),
            until=now + timedelta(seconds=policy.cooldown_seconds),
        )
    if probe_id is not None:
        raise CircuitDenied("circuit.unexpected_probe")
    if outcome is CircuitOutcome.SUCCESS:
        return CircuitState()
    if outcome is CircuitOutcome.DEFINITIVE_FAILURE:
        return state
    failures = state.failures + 1
    if failures < policy.threshold:
        return CircuitState(failures=failures)
    return CircuitState(
        phase=CircuitPhase.OPEN, failures=failures,
        until=now + timedelta(seconds=policy.cooldown_seconds),
    )
