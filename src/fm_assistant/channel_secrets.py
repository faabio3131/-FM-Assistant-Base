"""Cofre local de segredos de canais.

A chave mestra vem do ambiente/secret manager. O banco armazena apenas ciphertext.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class ChannelSecretBox:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("FM_ASSISTANT_CHANNEL_ENCRYPTION_KEY inválida") from exc

    def encrypt(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("channel_secret_required")
        return self._fernet.encrypt(normalized.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, TypeError) as exc:
            raise RuntimeError("channel_secret_decryption_failed") from exc
