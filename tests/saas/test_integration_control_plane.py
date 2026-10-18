from __future__ import annotations

import httpx
from sqlalchemy import create_engine, text


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _connect(client, api_key: str, *, phone_number_id: str = "phone-123"):
    response = client.post(
        "/v1/integrations",
        headers=_headers(api_key),
        json={
            "provider_key": "whatsapp_meta",
            "config": {
                "phone_number_id": phone_number_id,
                "business_account_id": "waba-123",
                "graph_api_version": "v23.0",
            },
            "secrets": {
                "access_token": "access-secret-1",
                "app_secret": "app-secret-1",
                "verify_token": "verify-secret-1",
            },
            "source": "tenant_managed",
        },
    )
    assert response.status_code == 200, response.text
    return response


def test_connect_masks_secrets_and_persists_ciphertext(
    client,
    provision_credential,
):
    api_key = provision_credential(client, "tenant-a", "unit-a")

    response = _connect(client, api_key)
    payload = response.json()

    assert payload["status"] == "draft"
    assert payload["provider_key"] == "whatsapp_meta"
    assert "secrets" not in payload
    assert "access-secret-1" not in response.text
    connection_id = payload["connection_id"]

    metadata = client.get(
        f"/v1/integrations/{connection_id}/secrets",
        headers=_headers(api_key),
    )
    assert metadata.status_code == 200, metadata.text
    rows = metadata.json()
    assert {row["secret_name"] for row in rows} == {
        "access_token",
        "app_secret",
        "verify_token",
    }
    assert all("ciphertext" not in row for row in rows)

    engine = create_engine(client.app.state.settings.database_url)
    with engine.connect() as connection:
        stored = connection.execute(
            text(
                """
                SELECT secret_name, ciphertext
                FROM assistant_integration_secret_versions
                WHERE connection_id = :connection_id
                """
            ),
            {"connection_id": connection_id},
        ).all()

    ciphertext_by_name = dict(stored)
    assert ciphertext_by_name["access_token"] != "access-secret-1"
    assert ciphertext_by_name["app_secret"] != "app-secret-1"
    assert ciphertext_by_name["verify_token"] != "verify-secret-1"


def test_validate_activate_rotate_revalidate_and_revoke(
    client,
    provision_credential,
    monkeypatch,
):
    api_key = provision_credential(client, "tenant-a", "unit-a")
    created = _connect(client, api_key)
    connection_id = created.json()["connection_id"]

    def fake_get(*args, **kwargs):
        return httpx.Response(200, json={"id": "phone-123"})

    monkeypatch.setattr("fm_assistant.integration_service.httpx.get", fake_get)

    validated = client.post(
        f"/v1/integrations/{connection_id}/validate",
        headers=_headers(api_key),
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["success"] is True

    activated = client.post(
        f"/v1/integrations/{connection_id}/activate",
        headers=_headers(api_key),
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"

    rotated = client.post(
        f"/v1/integrations/{connection_id}/rotate",
        headers=_headers(api_key),
        json={
            "secrets": {"access_token": "access-secret-2"},
            "source": "tenant_managed",
        },
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["status"] == "draft"
    assert rotated.json()["revision"] == 2

    stale_activation = client.post(
        f"/v1/integrations/{connection_id}/activate",
        headers=_headers(api_key),
    )
    assert stale_activation.status_code == 409
    assert stale_activation.json()["detail"] == "integration_validation_required"

    metadata = client.get(
        f"/v1/integrations/{connection_id}/secrets",
        headers=_headers(api_key),
    )
    assert metadata.status_code == 200
    access_versions = [
        row
        for row in metadata.json()
        if row["secret_name"] == "access_token"
    ]
    assert len(access_versions) == 2
    assert sorted(row["version"] for row in access_versions) == [1, 2]
    assert sum(1 for row in access_versions if row["active"]) == 1

    revalidated = client.post(
        f"/v1/integrations/{connection_id}/validate",
        headers=_headers(api_key),
    )
    assert revalidated.status_code == 200
    assert revalidated.json()["success"] is True
    assert revalidated.json()["revision"] == 2

    reactivated = client.post(
        f"/v1/integrations/{connection_id}/activate",
        headers=_headers(api_key),
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"

    disabled = client.post(
        f"/v1/integrations/{connection_id}/disable",
        headers=_headers(api_key),
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    revoked = client.post(
        f"/v1/integrations/{connection_id}/revoke",
        headers=_headers(api_key),
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    disabled_after_revoke = client.post(
        f"/v1/integrations/{connection_id}/disable",
        headers=_headers(api_key),
    )
    assert disabled_after_revoke.status_code == 409
    assert disabled_after_revoke.json()["detail"] == "integration_revoked"

    metadata_after = client.get(
        f"/v1/integrations/{connection_id}/secrets",
        headers=_headers(api_key),
    )
    assert metadata_after.status_code == 200
    assert all(not row["active"] for row in metadata_after.json())
    assert all(row["revoked_at"] is not None for row in metadata_after.json())


def test_remote_validation_failure_is_sanitized(
    client,
    provision_credential,
    monkeypatch,
):
    api_key = provision_credential(client, "tenant-a", "unit-a")
    connection_id = _connect(client, api_key).json()["connection_id"]

    def fake_get(*args, **kwargs):
        return httpx.Response(
            401,
            json={
                "error": {
                    "message": "provider says token access-secret-1 is invalid"
                }
            },
        )

    monkeypatch.setattr("fm_assistant.integration_service.httpx.get", fake_get)

    validated = client.post(
        f"/v1/integrations/{connection_id}/validate",
        headers=_headers(api_key),
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["success"] is False
    assert validated.json()["code"] == "provider_rejected"
    assert "access-secret-1" not in validated.text


def test_integration_isolation_between_tenants(
    client,
    provision_credential,
):
    key_a = provision_credential(client, "tenant-a", "unit-a")
    key_b = provision_credential(client, "tenant-b", "unit-b")
    connection_id = _connect(client, key_a).json()["connection_id"]

    listed_b = client.get("/v1/integrations", headers=_headers(key_b))
    assert listed_b.status_code == 200
    assert listed_b.json() == []

    secret_probe = client.get(
        f"/v1/integrations/{connection_id}/secrets",
        headers=_headers(key_b),
    )
    assert secret_probe.status_code == 404

    disable_probe = client.post(
        f"/v1/integrations/{connection_id}/disable",
        headers=_headers(key_b),
    )
    assert disable_probe.status_code == 404


def test_catalog_is_data_driven_and_has_no_secret_values(
    client,
    provision_credential,
):
    api_key = provision_credential(client, "tenant-a", "unit-a")
    response = client.get("/v1/integrations/catalog", headers=_headers(api_key))
    assert response.status_code == 200

    whatsapp = next(
        item
        for item in response.json()
        if item["provider_key"] == "whatsapp_meta"
    )
    assert whatsapp["integration_type"] == "whatsapp"
    assert set(whatsapp["secret_fields"]) == {
        "access_token",
        "app_secret",
        "verify_token",
    }
    assert "access-secret" not in response.text
