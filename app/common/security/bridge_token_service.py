from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import jwt

from app.common.config import get_settings


class BridgeAccessTokenService:
    def __init__(
        self,
        *,
        signing_key: str,
        algorithm: str,
        issuer: str,
        expire_seconds: int,
    ) -> None:
        self._signing_key = signing_key
        self._algorithm = algorithm
        self._issuer = issuer
        self._expire_seconds = expire_seconds

    def create_access_token(
        self,
        *,
        customer_id: int,
        instance_id: str,
        tenant_id: str,
        audience: str,
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": f"portal-bridge:{customer_id}:{instance_id}",
            "customer_id": str(customer_id),
            "instance_id": instance_id,
            "tenant_id": tenant_id,
            "aud": audience,
            "iss": self._issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._expire_seconds)).timestamp()),
            "jti": str(uuid4()),
            "token_type": "bridge_access",
            "scope": "zaraamad.bridge",
        }
        return jwt.encode(payload, self._signing_key, algorithm=self._algorithm)


def get_bridge_access_token_service() -> BridgeAccessTokenService:
    settings = get_settings()
    return BridgeAccessTokenService(
        signing_key=settings.jwt_signing_key,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        expire_seconds=settings.bridge_access_token_expire_seconds,
    )
