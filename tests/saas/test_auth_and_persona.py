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
