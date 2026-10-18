"""Vault universal de credenciais tenant/platform-owned."""

from __future__ import annotations

from typing import Protocol

from .channel_secrets import ChannelSecretBox


class CredentialVault(Protocol):
    def encrypt(self, value: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


class FernetCredentialVault:
    """Backend V1: ciphertext no banco e master key externa ao banco."""

    def __init__(self, key: str) -> None:
        self._box = ChannelSecretBox(key)

    def encrypt(self, value: str) -> str:
        return self._box.encrypt(value)

    def decrypt(self, ciphertext: str) -> str:
        return self._box.decrypt(ciphertext)
