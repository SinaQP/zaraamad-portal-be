from collections.abc import Mapping
from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from app.common.config import get_settings
from app.common.messages import INVALID_AUTH_TOKEN, INVALID_TOKEN_TYPE


class JWTService:
    def __init__(
        self,
        *,
        signing_key: str,
        algorithm: str,
        issuer: str,
        audience: str | None,
    ) -> None:
        self._signing_key = signing_key
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience.strip() if audience else None

    def decode_access_token(self, token: str) -> dict[str, Any]:
        decode_kwargs: dict[str, Any] = {
            "key": self._signing_key,
            "algorithms": [self._algorithm],
            "issuer": self._issuer,
            "options": {
                "verify_aud": self._audience is not None,
            },
        }
        if self._audience is not None:
            decode_kwargs["audience"] = self._audience
        try:
            payload = jwt.decode(token, **decode_kwargs)
        except (ExpiredSignatureError, JWTClaimsError, JWTError) as exc:
            raise ValueError(INVALID_AUTH_TOKEN) from exc
        if not isinstance(payload, Mapping):
            raise ValueError(INVALID_AUTH_TOKEN)
        token_type = payload.get("token_type")
        if token_type != "access":
            raise ValueError(INVALID_TOKEN_TYPE)
        return dict(payload)


def get_jwt_service() -> JWTService:
    settings = get_settings()
    return JWTService(
        signing_key=settings.jwt_signing_key,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
