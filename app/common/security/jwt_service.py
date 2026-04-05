from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from app.common.config import get_settings
from app.common.enums import UserRole
from app.common.messages import INVALID_AUTH_TOKEN, INVALID_TOKEN_TYPE


class JWTService:
    def __init__(
        self,
        *,
        signing_key: str,
        algorithm: str,
        issuer: str,
        audience: str | None,
        access_token_expire_minutes: int = 60,
    ) -> None:
        self._signing_key = signing_key
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience.strip() if audience else None
        self._access_token_expire_minutes = access_token_expire_minutes

    def create_access_token(self, *, user_id: int, mobile: str, role: UserRole) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "user_id": str(user_id),
            "mobile": mobile,
            "role": role.value,
            "roles": [self._role_claim_for(role)],
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(minutes=self._access_token_expire_minutes)).timestamp()
            ),
            "jti": str(uuid4()),
            "iss": self._issuer,
            "token_type": "access",
            # Preserve the legacy claim name for older clients that may inspect it.
            "type": "access",
        }
        if self._audience is not None:
            payload["aud"] = self._audience
        return jwt.encode(payload, self._signing_key, algorithm=self._algorithm)

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
        token_type = payload.get("token_type") or payload.get("type")
        if token_type != "access":
            raise ValueError(INVALID_TOKEN_TYPE)
        return dict(payload)

    def _role_claim_for(self, role: UserRole) -> str:
        if role == UserRole.ADMIN:
            return "Admin"
        if role == UserRole.CUSTOMER:
            return "Customer"
        return role.value


def get_jwt_service() -> JWTService:
    settings = get_settings()
    return JWTService(
        signing_key=settings.jwt_signing_key,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    )
