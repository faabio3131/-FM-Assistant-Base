"""Política interna de elegibilidade BYOK; não libera segredo nem abre API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fm_assistant.core_byok_release_policy import CoreBYOKReleasePolicy
from fm_assistant.db import (
    Base,
    EntitlementORM,
    IntegrationCapabilityORM,
    IntegrationConnectionORM,
    IntegrationProviderORM,
    IntegrationSecretVersionORM,
    TenantLicenseORM,
    TenantORM,
    UnitORM,
)


@pytest.fixture
def policy_db(tmp_path):
    now = datetime.now(UTC)
    engine = create_engine(f"sqlite:///{tmp_path / 'byok-eligibility.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(TenantORM(
            tenant_id="tenant-a", display_name="Tenant A", slug="tenant-a",
            status="active", created_at=now, updated_at=now,
        ))
        db.add(UnitORM(
            tenant_id="tenant-a", unit_id="unit-a", display_name="Unit A",
            status="active", created_at=now, updated_at=now,
        ))
        db.add(TenantLicenseORM(
            tenant_id="tenant-a", plan_code="pro", status="active",
            trial_started_at=None, trial_ends_at=None,
            period_started_at=now, period_ends_at=now + timedelta(days=30),
            created_at=now, updated_at=now,
        ))
        db.add(EntitlementORM(
            tenant_id="tenant-a", capability="ai.byok", enabled=True,
            limit_value=None, source="plan", updated_at=now,
        ))
        db.add(IntegrationProviderORM(
            provider_key="ai-test-provider", integration_type="ai",
            display_name="AI Test Provider", definition_version=1,
            enabled=True, created_at=now, updated_at=now,
        ))
        db.add(IntegrationConnectionORM(
            connection_id="connection-a", tenant_id="tenant-a", unit_id="unit-a",
            provider_key="ai-test-provider", integration_type="ai",
            status="active", config_json="{}", revision=1,
            created_at=now, updated_at=now,
        ))
        db.add(IntegrationCapabilityORM(
            connection_id="connection-a", capability="ai.text",
        ))
        db.add(IntegrationSecretVersionORM(
            connection_id="connection-a", secret_name="api_key", version=1,
            source="tenant_managed", storage_backend="db_encrypted",
            ciphertext="synthetic-ciphertext-not-a-live-secret",
            secret_reference=None, active=True, expires_at=now + timedelta(days=1),
            revoked_at=None, created_at=now,
        ))
    yield sessions
    engine.dispose()


def _eligible(sessions, **overrides) -> bool:
    kwargs = {
        "tenant_id": "tenant-a",
        "unit_id": "unit-a",
        "connection_id": "connection-a",
        "capability": "ai.text",
    }
    kwargs.update(overrides)
    return CoreBYOKReleasePolicy(sessions).eligible(**kwargs)


def test_active_tenant_unit_entitlement_provider_and_secret_are_required(policy_db):
    assert _eligible(policy_db) is True


@pytest.mark.parametrize(
    "override",
    [
        {"tenant_id": "tenant-b"},
        {"unit_id": "unit-b"},
        {"connection_id": "connection-b"},
        {"capability": "ai.audio"},
        {"tenant_id": ""},
        {"unit_id": ""},
    ],
)
def test_invalid_scope_is_denied_without_disclosure(policy_db, override):
    assert _eligible(policy_db, **override) is False


@pytest.mark.parametrize(
    "model,primary_key,field,new_value",
    [
        (TenantORM, "tenant-a", "status", "suspended"),
        (UnitORM, ("tenant-a", "unit-a"), "status", "disabled"),
        (TenantLicenseORM, "tenant-a", "status", "canceled"),
        (EntitlementORM, ("tenant-a", "ai.byok"), "enabled", False),
        (IntegrationProviderORM, "ai-test-provider", "enabled", False),
        (IntegrationProviderORM, "ai-test-provider", "integration_type", "whatsapp"),
        (IntegrationConnectionORM, "connection-a", "status", "revoked"),
        (IntegrationConnectionORM, "connection-a", "status", "draft"),
        (IntegrationSecretVersionORM, ("connection-a", "api_key", 1), "active", False),
        (IntegrationSecretVersionORM, ("connection-a", "api_key", 1), "source", "fm_managed"),
        (IntegrationSecretVersionORM, ("connection-a", "api_key", 1), "ciphertext", None),
    ],
)
def test_invalid_resource_or_plan_state_is_denied(
    policy_db, model, primary_key, field, new_value
):
    with policy_db.begin() as db:
        setattr(db.get(model, primary_key), field, new_value)
    assert _eligible(policy_db) is False


def test_expired_or_revoked_secret_is_denied(policy_db):
    with policy_db.begin() as db:
        secret = db.get(IntegrationSecretVersionORM, ("connection-a", "api_key", 1))
        secret.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert _eligible(policy_db) is False
    with policy_db.begin() as db:
        secret = db.get(IntegrationSecretVersionORM, ("connection-a", "api_key", 1))
        secret.expires_at = None
        secret.revoked_at = datetime.now(UTC)
    assert _eligible(policy_db) is False


def test_trial_requires_future_expiration(policy_db):
    with policy_db.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.status = "trial"
        license_row.trial_ends_at = datetime.now(UTC) - timedelta(seconds=1)
    assert _eligible(policy_db) is False
    with policy_db.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.trial_ends_at = datetime.now(UTC) + timedelta(days=1)
    assert _eligible(policy_db) is True


def test_policy_does_not_return_or_decrypt_secret_values(policy_db):
    result = _eligible(policy_db)
    assert type(result) is bool
    assert result is True



def test_expired_active_subscription_cannot_use_byok(policy_db):
    with policy_db.begin() as db:
        license_row = db.get(TenantLicenseORM, "tenant-a")
        license_row.period_ends_at = datetime.now(UTC) - timedelta(seconds=1)
    assert _eligible(policy_db) is False
