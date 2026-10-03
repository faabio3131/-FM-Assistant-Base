from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fm_assistant.api import create_app
from fm_assistant.settings import Environment, Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        environment=Environment.TEST,
        database_url=f"sqlite:///{tmp_path / 'assistant-test.db'}",
        admin_key="admin-test-key",
        credential_pepper="pepper-test-very-long",
        channel_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        model_backend="development",
        model_base_url=None,
        model_api_key=None,
        model_name=None,
        auto_create_schema=True,
    ).validate()
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def provision(client: TestClient, tenant_id: str, unit_id: str) -> str:
    response = client.post(
        "/v1/admin/credentials",
        headers={"X-Admin-Key": "admin-test-key"},
        json={"tenant_id": tenant_id, "unit_id": unit_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["api_key"]


@pytest.fixture
def provision_credential():
    return provision
