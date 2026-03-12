from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.common.database import Base, get_db_session
from app.common.dtos import CurrentUser
from app.common.enums import UserRole
from app.common.messages import (
    ADMIN_ACCESS_REQUIRED,
    INVALID_BRIDGE_KEY,
    MISSING_ACCESS_CREDENTIALS,
    MISSING_AUTH_TOKEN,
    TOKEN_SUBJECT_INVALID,
    TOKEN_SUBJECT_MISSING,
    USER_INACTIVE,
    USER_NOT_FOUND,
)
from app.common.security.jwt_service import JWTService, get_jwt_service

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Enter the JWT access token returned by /auth/verify-otp.",
)


class CurrentUserResolver:
    def __init__(self, jwt_service: JWTService) -> None:
        self._jwt_service = jwt_service

    def resolve(self, token: str, db_session: Session) -> CurrentUser:
        try:
            payload = self._jwt_service.decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=TOKEN_SUBJECT_MISSING,
            )
        try:
            parsed_user_id = int(user_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=TOKEN_SUBJECT_INVALID,
            ) from exc
        user_table = Base.metadata.tables["users"]
        row = db_session.execute(
            select(
                user_table.c.id,
                user_table.c.full_name,
                user_table.c.mobile,
                user_table.c.role,
                user_table.c.customer_id,
                user_table.c.is_active,
            ).where(user_table.c.id == parsed_user_id)
        ).mappings().first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=USER_NOT_FOUND,
            )
        if not row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=USER_INACTIVE,
            )
        return CurrentUser(
            id=row["id"],
            full_name=row["full_name"],
            mobile=row["mobile"],
            role=row["role"],
            customer_id=row["customer_id"],
            is_active=row["is_active"],
        )


@dataclass(frozen=True)
class RequestAccessContext:
    auth_mode: str
    current_user: CurrentUser | None
    correlation_id: str | None = None


class BridgeKeyAuthorizer:
    def __init__(self, bridge_api_key: str) -> None:
        self._bridge_api_key = bridge_api_key.strip()

    def authorize(self, provided_key: str | None) -> None:
        normalized_key = (provided_key or "").strip()
        if not normalized_key or normalized_key != self._bridge_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_BRIDGE_KEY,
            )


class AdminOrBridgeAccessResolver:
    def __init__(
        self,
        current_user_resolver: CurrentUserResolver,
        bridge_key_authorizer: BridgeKeyAuthorizer,
    ) -> None:
        self._current_user_resolver = current_user_resolver
        self._bridge_key_authorizer = bridge_key_authorizer

    def resolve(
        self,
        *,
        response: Response,
        credentials: HTTPAuthorizationCredentials | None,
        x_bridge_key: str | None,
        x_correlation_id: str | None,
        db_session: Session,
    ) -> RequestAccessContext:
        if x_bridge_key is not None:
            self._bridge_key_authorizer.authorize(provided_key=x_bridge_key)
            if x_correlation_id:
                response.headers["X-Correlation-ID"] = x_correlation_id
            return RequestAccessContext(
                auth_mode="bridge",
                current_user=None,
                correlation_id=x_correlation_id,
            )

        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=MISSING_ACCESS_CREDENTIALS,
            )

        current_user = self._current_user_resolver.resolve(
            token=credentials.credentials,
            db_session=db_session,
        )
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ADMIN_ACCESS_REQUIRED,
            )
        return RequestAccessContext(
            auth_mode="admin",
            current_user=current_user,
            correlation_id=x_correlation_id,
        )


def get_current_user_resolver(
    jwt_service: JWTService = Depends(get_jwt_service),
) -> CurrentUserResolver:
    return CurrentUserResolver(jwt_service=jwt_service)


def get_bridge_key_authorizer(
    settings: Settings = Depends(get_settings),
) -> BridgeKeyAuthorizer:
    return BridgeKeyAuthorizer(bridge_api_key=settings.bridge_api_key)


def get_admin_or_bridge_access_resolver(
    current_user_resolver: CurrentUserResolver = Depends(get_current_user_resolver),
    bridge_key_authorizer: BridgeKeyAuthorizer = Depends(get_bridge_key_authorizer),
) -> AdminOrBridgeAccessResolver:
    return AdminOrBridgeAccessResolver(
        current_user_resolver=current_user_resolver,
        bridge_key_authorizer=bridge_key_authorizer,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db_session: Session = Depends(get_db_session),
    resolver: CurrentUserResolver = Depends(get_current_user_resolver),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MISSING_AUTH_TOKEN,
        )
    token = credentials.credentials
    return resolver.resolve(token=token, db_session=db_session)


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ADMIN_ACCESS_REQUIRED,
        )
    return current_user


def require_admin_or_bridge_access(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_bridge_key: str | None = Header(
        default=None,
        alias="X-Bridge-Key",
        description="Shared secret used for bridge-to-bridge requests.",
    ),
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id echoed for bridge requests.",
    ),
    db_session: Session = Depends(get_db_session),
    resolver: AdminOrBridgeAccessResolver = Depends(get_admin_or_bridge_access_resolver),
) -> RequestAccessContext:
    return resolver.resolve(
        response=response,
        credentials=credentials,
        x_bridge_key=x_bridge_key,
        x_correlation_id=x_correlation_id,
        db_session=db_session,
    )
