from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.common.dtos import CurrentUser
from app.common.enums import UserRole
from app.common.security.jwt_service import JWTService, get_jwt_service

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Enter the JWT access token from /auth/verify-otp.",
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
                detail="Token subject is missing.",
            )
        try:
            parsed_user_id = int(user_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token subject is invalid.",
            ) from exc
        user_table = Base.metadata.tables["users"]
        row = db_session.execute(
            select(
                user_table.c.id,
                user_table.c.full_name,
                user_table.c.mobile,
                user_table.c.role,
                user_table.c.municipality_id,
                user_table.c.is_active,
            ).where(user_table.c.id == parsed_user_id)
        ).mappings().first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
            )
        if not row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is inactive.",
            )
        return CurrentUser(
            id=row["id"],
            full_name=row["full_name"],
            mobile=row["mobile"],
            role=row["role"],
            municipality_id=row["municipality_id"],
            is_active=row["is_active"],
        )


def get_current_user_resolver(
    jwt_service: JWTService = Depends(get_jwt_service),
) -> CurrentUserResolver:
    return CurrentUserResolver(jwt_service=jwt_service)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db_session: Session = Depends(get_db_session),
    resolver: CurrentUserResolver = Depends(get_current_user_resolver),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
        )
    token = credentials.credentials
    return resolver.resolve(token=token, db_session=db_session)


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user
