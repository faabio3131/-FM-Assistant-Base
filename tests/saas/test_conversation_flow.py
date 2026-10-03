def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_knowledge_conversation_message_and_handoff(client, provision_credential):
    key = provision_credential(client, "tenant-sales", "unit-sp")

    persona = client.put(
        "/v1/persona",
        headers=_headers(key),
        json={
            "public_name": "Nina",
            "language": "pt-BR",
            "tone": "consultivo",
            "instructions": "Nunca invente preço.",
            "enabled": True,
        },
    )
    assert persona.status_code == 200

    knowledge = client.post(
        "/v1/knowledge",
        headers=_headers(key),
        json={
            "title": "Produto Alpha",
            "content": "Produto Alpha é o plano inicial da empresa.",
        },
    )
    assert knowledge.status_code == 200

    created = client.post(
        "/v1/conversations",
        headers=_headers(key),
        json={"channel": "webchat", "external_ref": "visitor-123"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]

    reply = client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers=_headers(key),
        json={"content": "O que vocês oferecem?"},
    )
    assert reply.status_code == 200
    assert reply.json()["role"] == "assistant"
    assert "Nina" in reply.json()["content"]

    history = client.get(
        f"/v1/conversations/{conversation_id}/messages",
        headers=_headers(key),
    )
    assert history.status_code == 200
    assert [item["role"] for item in history.json()] == ["user", "assistant"]

    handoff = client.post(
        f"/v1/conversations/{conversation_id}/handoff",
        headers=_headers(key),
        json={"reason": "Cliente pediu uma pessoa"},
    )
    assert handoff.status_code == 200
    assert handoff.json()["status"] == "human_handoff"

    after_handoff = client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers=_headers(key),
        json={"content": "Nova mensagem"},
    )
    assert after_handoff.status_code == 409
