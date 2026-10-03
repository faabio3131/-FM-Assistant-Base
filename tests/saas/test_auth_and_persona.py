def test_admin_key_is_required(client):
    response = client.post(
        "/v1/admin/credentials",
        json={"tenant_id": "tenant-a", "unit_id": "unit-a"},
    )
    assert response.status_code == 403


def test_tenant_can_configure_own_persona(client, provision_credential):
    api_key = provision_credential(client, "tenant-a", "unit-a")
    headers = {"Authorization": f"Bearer {api_key}"}

    response = client.put(
        "/v1/persona",
        headers=headers,
        json={
            "public_name": "Luna",
            "language": "pt-BR",
            "tone": "consultivo",
            "instructions": "Seja objetiva.",
            "enabled": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["public_name"] == "Luna"

    fetched = client.get("/v1/persona", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["tone"] == "consultivo"


def test_revoked_credential_cannot_be_used(client, provision_credential):
    response = client.post(
        "/v1/admin/credentials",
        headers={"X-Admin-Key": "admin-test-key"},
        json={"tenant_id": "tenant-r", "unit_id": "unit-r"},
    )
    assert response.status_code == 200
    payload = response.json()
    api_key = payload["api_key"]
    credential_id = payload["credential_id"]

    configured = client.put(
        "/v1/persona",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "public_name": "Rita",
            "language": "pt-BR",
            "tone": "profissional",
            "instructions": "",
            "enabled": True,
        },
    )
    assert configured.status_code == 200

    revoked = client.delete(
        f"/v1/admin/credentials/{credential_id}",
        headers={"X-Admin-Key": "admin-test-key"},
    )
    assert revoked.status_code == 204

    denied = client.get(
        "/v1/persona",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert denied.status_code == 401
