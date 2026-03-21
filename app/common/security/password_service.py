import hashlib
from secrets import compare_digest, token_hex


class PasswordService:
    _ALGORITHM = "pbkdf2_sha256"
    _ITERATIONS = 200_000
    _SALT_BYTES = 16
    _DIGEST_BYTES = 32

    def hash_password(self, password: str) -> str:
        salt_hex = token_hex(self._SALT_BYTES)
        digest_hex = self._derive_digest_hex(password=password, salt_hex=salt_hex, iterations=self._ITERATIONS)
        return f"{self._ALGORITHM}${self._ITERATIONS}${salt_hex}${digest_hex}"

    def verify_password(self, password: str, stored_password: str | None) -> bool:
        if not stored_password:
            return False
        if self.is_hashed_password(stored_password):
            try:
                _, iterations_text, salt_hex, expected_digest_hex = stored_password.split("$", 3)
                iterations = int(iterations_text)
                actual_digest_hex = self._derive_digest_hex(
                    password=password,
                    salt_hex=salt_hex,
                    iterations=iterations,
                )
            except (TypeError, ValueError):
                return False
            return compare_digest(actual_digest_hex, expected_digest_hex)
        return compare_digest(password, stored_password)

    def is_hashed_password(self, stored_password: str | None) -> bool:
        return bool(stored_password and stored_password.startswith(f"{self._ALGORITHM}$"))

    def is_legacy_plaintext_password(self, stored_password: str | None) -> bool:
        return bool(stored_password) and not self.is_hashed_password(stored_password)

    def _derive_digest_hex(self, password: str, salt_hex: str, iterations: int) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
            dklen=self._DIGEST_BYTES,
        ).hex()


def get_password_service() -> PasswordService:
    return PasswordService()
