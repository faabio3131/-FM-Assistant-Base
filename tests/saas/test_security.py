from fm_assistant.security import generate_api_key, hash_api_key


def test_api_keys_are_random_and_hashed():
    first = generate_api_key()
    second = generate_api_key()

    assert first.startswith("fma_")
    assert second.startswith("fma_")
    assert first != second

    digest = hash_api_key(first, "pepper")
    assert len(digest) == 64
    assert first not in digest
