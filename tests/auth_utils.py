from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from sqlalchemy import select

from app.common.config import get_settings
from app.common.database import get_db_session
from app.common.enums import UserRole
from app.main import app
from app.modules.users.schemas import User

_AUDIENCE_UNSET = object()


def build_access_token(
    *,
    subject: str,
    user_id: str | None = None,
    roles: list[str] | None = None,
    security_stamp: str | None = "stamp-123",
    issuer: str | None = None,
    audience: str | None | object = _AUDIENCE_UNSET,
    signing_key: str | None = None,
    algorithm: str | None = None,
    token_type: str = "access",
    expires_delta: timedelta = timedelta(hours=1),
    include_sub: bool = True,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    resolved_audience = settings.jwt_audience if audience is _AUDIENCE_UNSET else audience
    payload: dict[str, Any] = {
        "token_type": token_type,
        "exp": int((issued_at + expires_delta).timestamp()),
        "iat": int(issued_at.timestamp()),
        "jti": "test-jti",
        "user_id": user_id or subject,
        "roles": roles or [],
        "security_stamp": security_stamp,
        "iss": issuer or settings.jwt_issuer,
    }
    if include_sub:
        payload["sub"] = subject
    if resolved_audience is not None:
        payload["aud"] = resolved_audience
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        signing_key or settings.jwt_signing_key,
        algorithm=algorithm or settings.jwt_algorithm,
    )


def access_token_for_user(
    user: User,
    *,
    roles: list[str] | None = None,
    security_stamp: str | None = "stamp-123",
) -> str:
    return build_access_token(
        subject=str(user.id),
        user_id=str(user.id),
        roles=roles or role_claims_for_user(user),
        security_stamp=security_stamp,
    )


def auth_headers_for_user(
    user: User,
    *,
    roles: list[str] | None = None,
    security_stamp: str | None = "stamp-123",
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token_for_user(user, roles=roles, security_stamp=security_stamp)}"
    }


def token_for_mobile(mobile: str, *, roles: list[str] | None = None) -> str:
    user = _get_user_by_mobile(mobile=mobile)
    return access_token_for_user(user, roles=roles)


def role_claims_for_user(user: User) -> list[str]:
    if user.role == UserRole.ADMIN:
        return ["Admin"]
    if user.role == UserRole.CUSTOMER:
        return ["Customer"]
    if user.role == UserRole.PUBLIC:
        return ["Public"]
    return []


def _get_user_by_mobile(*, mobile: str) -> User:
    override = app.dependency_overrides.get(get_db_session)
    if override is None:
        raise RuntimeError("Database override is not configured for the current test.")
    session_generator = override()
    try:
        session = next(session_generator)
        user = session.execute(
            select(User).where(User.mobile == mobile)
        ).scalar_one()
        return user
    except StopIteration as exc:
        raise RuntimeError("Database override did not yield a session.") from exc
    finally:
        try:
            next(session_generator)
        except StopIteration:
            pass
