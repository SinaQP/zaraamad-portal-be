from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import JWTError, jwt

from app.common.config import get_settings
from app.common.enums import UserRole
from app.common.messages import INVALID_AUTH_TOKEN, INVALID_TOKEN_TYPE


class JWTService:
    def __init__(
        self,
        secret_key: str,
        algorithm: str,
        access_token_expire_minutes: int,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes

    def create_access_token(self, user_id: int, mobile: str, role: UserRole) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "mobile": mobile,
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._access_token_expire_minutes)).timestamp()),
            "jti": str(uuid4()),
            "type": "access",
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> dict[str, str | int]:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except JWTError as exc:
            raise ValueError(INVALID_AUTH_TOKEN) from exc
        token_type = payload.get("type")
        if token_type != "access":
            raise ValueError(INVALID_TOKEN_TYPE)
        return payload


def get_jwt_service() -> JWTService:
    settings = get_settings()
    return JWTService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    )
