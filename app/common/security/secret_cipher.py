from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends

from app.common.config import Settings, get_settings


class SecretCipherConfigurationError(Exception):
    pass


class SecretCipherDecryptionError(Exception):
    pass


class SecretCipherService:
    def __init__(self, secret_key: str | None) -> None:
        self._secret_key = self._normalize_secret_key(secret_key)

    def encrypt(self, plaintext: str) -> str:
        fernet = self._build_fernet()
        return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        fernet = self._build_fernet()
        try:
            decrypted_bytes = fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken as exc:
            raise SecretCipherDecryptionError(
                "Stored database connection secret could not be decrypted."
            ) from exc
        return decrypted_bytes.decode("utf-8")

    def fingerprint(self, plaintext: str) -> str:
        return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

    def _build_fernet(self) -> Fernet:
        if self._secret_key is None:
            raise SecretCipherConfigurationError(
                "Customer connection secret key is not configured."
            )
        try:
            return Fernet(self._secret_key.encode("utf-8"))
        except ValueError as exc:
            raise SecretCipherConfigurationError(
                "Customer connection secret key is invalid."
            ) from exc

    def _normalize_secret_key(self, secret_key: str | None) -> str | None:
        if secret_key is None:
            return None
        normalized_secret_key = secret_key.strip()
        return normalized_secret_key or None


def get_secret_cipher_service(
    settings: Settings = Depends(get_settings),
) -> SecretCipherService:
    return SecretCipherService(
        secret_key=settings.customer_connection_secret_key,
    )
