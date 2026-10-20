"""F3 PostgreSQL gate: real row locks, service replay and revocation.

Runs only with an isolated disposable database in CI. No production URL
or live secrets are accepted; every row is synthetic and test-scoped.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from fm_assistant.command_bridge_control_models import (
    CommandBridgeControlEventORM,
    CommandBridgeStatusNonceORM,
)
from fm_assistant.command_bridge_control_service import (
    STATUS_PATH,
    CommandBridgeControlService,
    CommandBridgeDenied,
    sign_command_control,
)
from fm_assistant.core_bridge_models import (
    CoreBridgeAccessORM,
    CoreBridgeGrantORM,
    CoreBridgeIdentityORM,
)
from fm_assistant.core_bridge_service import (
    CoreBridgeDenied,
    CoreBridgeService,
    sign_core_bridge,
)
from fm_assistant.credential_vault import FernetCredentialVault
from fm_assistant.db import (
    EntitlementORM,
    IntegrationCapabilityORM,
    IntegrationConnectionORM,
    IntegrationProviderORM,
    IntegrationSecretVersionORM,
    TenantLicenseORM,
    TenantORM,
    UnitORM,
)

CORE_KEY_ID = "test-core-service"
COMMAND_KEY_ID = "test-command-service"
CORE_KEY = "postgres-test-core-hmac-key-synthetic-only"
COMMAND_KEY = "postgres-test-command-hmac-key-synthetic-only"
ORG = "fm-platform-fixture"
VAULT_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
TENANT_ID = "tenant-postgres"
UNIT_ID = "unit-postgres"
CAPABILITY = "ai.text"
CONNECTION_ID = "test-ai-connection"
CORE_PATH = "/internal/v1/core/credentials/resolve"
COMMAND_PATH = "/internal/v1/command/core-bridge/manage"


def _signed_core(nonce: str) -> tuple[dict[str, str], bytes]:
    import json

    body = json.dumps(
        {
            "tenant_id": TENANT_ID,
            "unit_id": UNIT_ID,
            "capability": CAPABILITY,
            "connection_id": CONNECTION_ID,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    return (
        {
            "key_id": CORE_KEY_ID,
            "timestamp": timestamp,
            "nonce": nonce,
            "signature": sign_core_bridge(
                key=CORE_KEY, key_id=CORE_KEY_ID,
                timestamp=timestamp, nonce=nonce, body=body,
            ),
        },
        body,
    )


def _signed_command(action: str) -> tuple[dict[str, str], bytes, dict]:
    import json

    data = {
        "action": action,
        "tenant_id": TENANT_ID,
        "unit_id": UNIT_ID,
        "capability": CAPABILITY,
        "target_key_id": CORE_KEY_ID,
        "actor_user_id": "fm-admin-fixture",
        "organization_id": ORG,
        "step_up_at": int(datetime.now(UTC).timestamp()),
        "command_request_id": str(uuid4()),
    }
    body = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    nonce = secrets.token_urlsafe(24)
    return (
        {
            "key_id": COMMAND_KEY_ID,
            "timestamp": timestamp,
            "nonce": nonce,
            "signature": sign_command_control(
                key=COMMAND_KEY, key_id=COMMAND_KEY_ID,
                timestamp=timestamp, nonce=nonce, body=body,
            ),
        },
        body,
        data,
    )


@pytest.fixture
def postgres_bridge():
    url = os.getenv("FM_ASSISTANT_F3_POSTGRES_TEST_URL")
    if not url or "assistant_f3" not in url:
        pytest.skip("requires isolated assistant_f3 PostgreSQL test database")
    assert url.startswith("postgresql+psycopg://"), "unsafe test database dialect"
    upgrade_env = os.environ.copy()
    upgrade_env["FM_ASSISTANT_DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True, env=upgrade_env, capture_output=True, text=True,
    )
    engine = create_engine(url, pool_size=6, max_overflow=4, pool_timeout=10)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)
    vault = FernetCredentialVault(VAULT_KEY)
    # Disposable assistant_f3 ONLY. Each test gets a clean, migrated schema.
    with engine.begin() as cleanup:
        cleanup.execute(text("DELETE FROM assistant_command_bridge_status_nonce"))
        cleanup.execute(text(
            "TRUNCATE TABLE assistant_tenants, assistant_integration_providers, "
            "assistant_core_bridge_identities RESTART IDENTITY CASCADE"
        ))
    with sessions.begin() as db:
        db.add(TenantORM(
            tenant_id=TENANT_ID, display_name="Postgres Fixture", slug=TENANT_ID,
            status="active", created_at=now, updated_at=now,
        ))
        db.flush()  # PostgreSQL FK: tenant must exist before dependent rows.
        db.add(UnitORM(
            tenant_id=TENANT_ID, unit_id=UNIT_ID, display_name="Unit",
            status="active", created_at=now, updated_at=now,
        ))
        db.flush()  # PostgreSQL FK: unit must exist before bridge grants.
        db.add(TenantLicenseORM(
            tenant_id=TENANT_ID, plan_code="test", status="active",
            trial_started_at=None, trial_ends_at=None,
            period_started_at=now, period_ends_at=now + timedelta(hours=4),
            created_at=now, updated_at=now,
        ))
        db.add(EntitlementORM(
            tenant_id=TENANT_ID, capability="ai.byok",
            enabled=True, limit_value=None, source="test", updated_at=now,
        ))
        db.add(IntegrationProviderORM(
            provider_key="ai-fixture", integration_type="ai",
            display_name="AI Fixture", definition_version=1,
            enabled=True, created_at=now, updated_at=now,
        ))
        db.flush()  # Provider FK before connection registration.
        db.add(IntegrationConnectionORM(
            connection_id=CONNECTION_ID,
            tenant_id=TENANT_ID, unit_id=UNIT_ID,
            provider_key="ai-fixture", integration_type="ai",
            status="active", config_json="{}", revision=1,
            created_at=now, updated_at=now,
        ))
        db.flush()  # Connection FK before capabilities and secret versions.
        db.add(IntegrationCapabilityORM(
            connection_id=CONNECTION_ID, capability=CAPABILITY,
        ))
        db.add(IntegrationSecretVersionORM(
            connection_id=CONNECTION_ID, secret_name="api_key",
            version=1, source="tenant_managed", storage_backend="db_encrypted",
            ciphertext=vault.encrypt("synthetic-test-token-123"),
            secret_reference=None, active=True,
            expires_at=now + timedelta(hours=1), revoked_at=None,
            created_at=now,
        ))
        db.add(CoreBridgeIdentityORM(
            key_id=CORE_KEY_ID, active=True, revoked_at=None, created_at=now,
        ))
        # Flush the parent tenant, unit and identity before the FK-dependent grant.
        db.flush()
        db.add(CoreBridgeGrantORM(
            key_id=CORE_KEY_ID, tenant_id=TENANT_ID, unit_id=UNIT_ID,
            capability=CAPABILITY, active=True, revoked_at=None, created_at=now,
        ))
    core = CoreBridgeService(
        sessions=sessions, vault=vault,
        key_id=CORE_KEY_ID, signing_key=CORE_KEY,
    )
    command = CommandBridgeControlService(
        sessions=sessions,
        command_key_id=COMMAND_KEY_ID,
        command_signing_key=COMMAND_KEY,
        trusted_organization=ORG,
        core_key_id=CORE_KEY_ID,
    )
    try:
        yield sessions, core, command
    finally:
        # CI provisions a disposable database and discards it after the job.
        engine.dispose()


def _resolve(core: CoreBridgeService, nonce: str) -> str:
    headers, body = _signed_core(nonce)
    return core.resolve(
        headers=headers, raw_body=body,
        tenant_id=TENANT_ID, unit_id=UNIT_ID,
        capability=CAPABILITY, connection_id=CONNECTION_ID,
    )


def _command(command: CommandBridgeControlService, action: str) -> str:
    headers, body, payload = _signed_command(action)
    return command.execute(raw_body=body, headers=headers, **payload)


def test_postgres_simultaneous_duplicate_nonce_allows_one_release(postgres_bridge):
    sessions, core, _ = postgres_bridge
    shared_nonce = secrets.token_urlsafe(24)
    barrier = Barrier(2)

    def attempt() -> str:
        barrier.wait(timeout=5)
        try:
            return _resolve(core, shared_nonce)
        except CoreBridgeDenied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(attempt)
        b = pool.submit(attempt)
        outcomes = [a.result(timeout=15), b.result(timeout=15)]
    assert sorted(outcomes) == ["denied", "synthetic-test-token-123"]
    with sessions() as db:
        logs = db.scalars(
            select(CoreBridgeAccessORM).where(CoreBridgeAccessORM.nonce == shared_nonce)
        ).all()
        assert len(logs) == 1
        assert logs[0].outcome == "released"


def test_postgres_command_revoke_persists_before_next_core_request(postgres_bridge):
    sessions, core, command = postgres_bridge
    assert _resolve(core, secrets.token_urlsafe(24)) == "synthetic-test-token-123"
    assert _command(command, "revoke_grant") == "revoked"
    with pytest.raises(CoreBridgeDenied, match="core_bridge_denied"):
        _resolve(core, secrets.token_urlsafe(24))
    with sessions() as db:
        grant = db.get(CoreBridgeGrantORM, (CORE_KEY_ID, TENANT_ID, UNIT_ID, CAPABILITY))
        assert not grant.active and grant.revoked_at is not None
        outcomes = [x.outcome for x in db.scalars(select(CoreBridgeAccessORM)).all()]
        assert "released" in outcomes and "denied" in outcomes
        records = db.scalars(select(CommandBridgeControlEventORM)).all()
        assert len(records) == 1 and records[0].outcome == "revoked"


def test_postgres_command_identity_revocation_is_irreversible(postgres_bridge):
    sessions, core, command = postgres_bridge
    assert _command(command, "revoke_identity") == "revoked"
    with pytest.raises(CoreBridgeDenied):
        _resolve(core, secrets.token_urlsafe(24))
    with pytest.raises(CommandBridgeDenied):
        _command(command, "provision")
    with sessions() as db:
        identity = db.get(CoreBridgeIdentityORM, CORE_KEY_ID)
        assert not identity.active and identity.revoked_at is not None
        assert not db.get(
            CoreBridgeGrantORM, (CORE_KEY_ID, TENANT_ID, UNIT_ID, CAPABILITY)
        ).active


def test_postgres_status_nonce_concurrent_replay_allows_one_read(postgres_bridge):
    """A signed status lookup cannot be replayed, including concurrently."""
    sessions, _, command = postgres_bridge
    headers, body, payload = _signed_command("grant")
    headers["signature"] = sign_command_control(
        key=COMMAND_KEY, key_id=COMMAND_KEY_ID,
        timestamp=headers["timestamp"], nonce=headers["nonce"],
        body=body, path=STATUS_PATH,
    )
    barrier = Barrier(2)
    with sessions() as db:
        # Previous tests may leave immutable control events: measure delta.
        baseline_events = len(db.scalars(select(CommandBridgeControlEventORM)).all())

    def attempt() -> str:
        barrier.wait(timeout=5)
        try:
            return command.reconcile_status(
                raw_body=body, headers=headers, **payload,
            )["status"]
        except CommandBridgeDenied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(attempt)
        b = pool.submit(attempt)
        outcomes = [a.result(timeout=15), b.result(timeout=15)]
    assert sorted(outcomes) == ["denied", "unknown"]
    with sessions() as db:
        rows = db.scalars(select(CommandBridgeStatusNonceORM)).all()
        assert len(rows) == 1
        assert rows[0].command_request_id == payload["command_request_id"]
        # No mutation events are added by read-only status inquiries.
        assert len(db.scalars(select(CommandBridgeControlEventORM)).all()) == baseline_events
        grant = db.get(
            CoreBridgeGrantORM, (CORE_KEY_ID, TENANT_ID, UNIT_ID, CAPABILITY)
        )
        assert grant and grant.active


def test_postgres_queue_capacity_is_atomic_across_ingress_replicas(postgres_bridge):
    """Two producers against a one-slot queue cannot both be acknowledged."""
    from fm_assistant.evolution_queue import (
        EvolutionInboundQueue,
        EvolutionQueueCapacityExceeded,
    )

    sessions, _, _ = postgres_bridge
    queue = EvolutionInboundQueue(
        sessions, FernetCredentialVault(VAULT_KEY), max_pending_per_connection=1,
    )
    gate = Barrier(2)

    def produce(number: int) -> str:
        gate.wait(timeout=10)
        try:
            accepted = queue.enqueue(
                connection_id=CONNECTION_ID, message_id=f"PG-CAP-{number}",
                sender="5511999999999", text="private synthetic event",
            )
            return "accepted" if accepted else "duplicate"
        except EvolutionQueueCapacityExceeded:
            return "full"

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(produce, i) for i in range(2)]
        results = [job.result(timeout=20) for job in jobs]
    assert sorted(results) == ["accepted", "full"]
    status = queue.operational_snapshot(connection_id=CONNECTION_ID)
    assert status["counts"]["pending"] == 1
    assert "5511999999999" not in str(status)


def test_postgres_queue_eight_workers_claim_at_most_once(postgres_bridge):
    from fm_assistant.evolution_queue import EvolutionInboundQueue

    sessions, _, _ = postgres_bridge
    queue = EvolutionInboundQueue(
        sessions, FernetCredentialVault(VAULT_KEY),
    )
    assert queue.enqueue(
        connection_id=CONNECTION_ID, message_id="PG-ONCE",
        sender="5511999999999", text="one and only",
    )
    gate = Barrier(8)

    def claim_once(_: int) -> str | None:
        gate.wait(timeout=10)
        item = queue.claim()
        return item.message_id if item else None

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(claim_once, i) for i in range(8)]
        results = [future.result(timeout=20) for future in futures]
    assert results.count("PG-ONCE") == 1
    assert results.count(None) == 7
    assert queue.state(connection_id=CONNECTION_ID, message_id="PG-ONCE") == "processing"
    queue.finish(
        connection_id=CONNECTION_ID, message_id="PG-ONCE", reconciled=True,
        code="synthetic_uncertain_outcome",
    )
    assert queue.quarantine_stale() == 0
    assert queue.claim() is None


@pytest.mark.parametrize("terminal_state", ["disabled", "revoked"])
def test_postgres_send_lock_serializes_pause_and_revoke(
    postgres_bridge, terminal_state,
):
    """Real PostgreSQL row-lock contention, not SQLite FOR UPDATE emulation."""
    from fm_assistant.domain import TenantContext
    from fm_assistant.evolution_queue import EvolutionInboundQueue
    from fm_assistant.integration import IntegrationStatus
    from fm_assistant.integration_repository import IntegrationRepository

    sessions, _, _ = postgres_bridge
    with sessions.begin() as db:
        db.add(IntegrationProviderORM(
            provider_key="whatsapp_evolution", integration_type="channel",
            display_name="Evolution Fixture", definition_version=1,
            enabled=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
    with sessions.begin() as db:
        row = db.get(IntegrationConnectionORM, CONNECTION_ID)
        row.provider_key = "whatsapp_evolution"
        row.integration_type = "channel"
    queue = EvolutionInboundQueue(sessions, FernetCredentialVault(VAULT_KEY))
    repository = IntegrationRepository(sessions)
    context = TenantContext(
        tenant_id=TENANT_ID, unit_id=UNIT_ID, credential_id="synthetic-worker",
    )
    acquired = Event()
    release = Event()
    mutation_done = Event()

    def outbound() -> str:
        with queue.outbound_connection_guard(
            connection_id=CONNECTION_ID, expected_revision=1,
        ):
            acquired.set()
            assert release.wait(timeout=10)
            with sessions() as verify:
                # PostgreSQL MVCC: another transaction must not have
                # committed a terminal change while send lock is held.
                row = verify.get(IntegrationConnectionORM, CONNECTION_ID)
                assert row.status == "active" and row.revision == 1
        return "released"

    def mutate() -> str:
        assert acquired.wait(timeout=10)
        result = repository.update_connection(
            context, CONNECTION_ID,
            status=IntegrationStatus(terminal_state), bump_revision=True,
        )
        mutation_done.set()
        return result.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        running_send = pool.submit(outbound)
        running_mutation = pool.submit(mutate)
        assert acquired.wait(timeout=10)
        # The mutator must block on the row lock while the HTTP phase holds it.
        assert not mutation_done.wait(timeout=0.25)
        release.set()
        assert running_send.result(timeout=10) == "released"
        assert running_mutation.result(timeout=10) == terminal_state
    with pytest.raises(PermissionError, match="evolution_connection_changed_before_send"):
        with queue.outbound_connection_guard(
            connection_id=CONNECTION_ID, expected_revision=1,
        ):
            pass
