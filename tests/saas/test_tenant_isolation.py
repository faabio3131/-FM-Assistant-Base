def _configure(client, api_key: str, name: str) -> None:
    response = client.put(
        "/v1/persona",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "public_name": name,
            "language": "pt-BR",
            "tone": "profissional",
            "instructions": "",
            "enabled": True,
        },
    )
    assert response.status_code == 200


def test_conversation_cannot_cross_tenant_boundary(client, provision_credential):
    key_a = provision_credential(client, "tenant-a", "unit-a")
    key_b = provision_credential(client, "tenant-b", "unit-b")
    _configure(client, key_a, "Atendente A")
    _configure(client, key_b, "Atendente B")

    created = client.post(
        "/v1/conversations",
        headers={"Authorization": f"Bearer {key_a}"},
        json={"channel": "api"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]

    foreign_read = client.get(
        f"/v1/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {key_b}"},
    )
    assert foreign_read.status_code == 404

    foreign_message = client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {key_b}"},
        json={"content": "Tente acessar a conversa do outro tenant"},
    )
    assert foreign_message.status_code == 404
