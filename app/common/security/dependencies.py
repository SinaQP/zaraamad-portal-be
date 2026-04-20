from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.common.dtos import CurrentUser
from app.common.enums import UserRole
from app.common.messages import (
    ADMIN_ACCESS_REQUIRED,
    MISSING_AUTH_TOKEN,
    TOKEN_SUBJECT_MISSING,
)
from app.common.security.jwt_service import JWTService, get_jwt_service

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Enter the Django-issued JWT access token.",
)


class LocalUserHydrator:
    def hydrate(self, *, subject: str, db_session: Session) -> dict[str, Any] | None:
        try:
            local_user_id = int(subject)
        except (TypeError, ValueError):
            return None
        user_table = Base.metadata.tables["users"]
        row = db_session.execute(
            select(
                user_table.c.id,
                user_table.c.full_name,
                user_table.c.mobile,
                user_table.c.role,
                user_table.c.customer_id,
                user_table.c.is_active,
            ).where(user_table.c.id == local_user_id)
        ).mappings().first()
        if row is None or not row["is_active"]:
            return None
        return dict(row)


class SecurityStampValidator:
    def validate(self, *, current_user: CurrentUser, db_session: Session) -> None:
        # Phase one intentionally treats the JWT security stamp as a verified claim only.
        del current_user, db_session


class CurrentUserResolver:
    def __init__(
        self,
        *,
        jwt_service: JWTService,
        local_user_hydrator: LocalUserHydrator,
        security_stamp_validator: SecurityStampValidator,
    ) -> None:
        self._jwt_service = jwt_service
        self._local_user_hydrator = local_user_hydrator
        self._security_stamp_validator = security_stamp_validator

    def resolve(self, *, token: str, db_session: Session) -> CurrentUser:
        try:
            payload = self._jwt_service.decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        subject = self._resolve_subject(payload=payload)
        roles = self._normalize_roles(payload.get("roles"))
        local_user = self._local_user_hydrator.hydrate(
            subject=subject,
            db_session=db_session,
        )
        current_user = CurrentUser(
            user_id=subject,
            sub=self._as_string(payload.get("sub")),
            roles=roles,
            security_stamp=self._as_string(payload.get("security_stamp")),
            raw_claims=payload,
            id=local_user["id"] if local_user else None,
            full_name=self._as_string(local_user["full_name"]) if local_user else None,
            mobile=self._as_string(local_user["mobile"]) if local_user else None,
            role=self._resolve_role(
                roles=roles,
                local_role=local_user["role"] if local_user else None,
            ),
            customer_id=local_user["customer_id"] if local_user else None,
            is_active=bool(local_user["is_active"]) if local_user is not None else None,
        )
        self._security_stamp_validator.validate(
            current_user=current_user,
            db_session=db_session,
        )
        return current_user

    def _resolve_subject(self, *, payload: dict[str, Any]) -> str:
        subject = payload.get("sub") or payload.get("user_id")
        subject_text = self._as_string(subject)
        if not subject_text:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=TOKEN_SUBJECT_MISSING,
            )
        return subject_text

    def _normalize_roles(self, raw_roles: Any) -> list[str]:
        if raw_roles is None:
            return []
        if isinstance(raw_roles, str):
            normalized = raw_roles.strip()
            return [normalized] if normalized else []
        if isinstance(raw_roles, list):
            roles: list[str] = []
            for value in raw_roles:
                normalized = self._as_string(value)
                if normalized:
                    roles.append(normalized)
            return roles
        return []

    def _resolve_role(
        self,
        *,
        roles: list[str],
        local_role: Any,
    ) -> UserRole | None:
        if isinstance(local_role, UserRole):
            return local_role
        if isinstance(local_role, str):
            try:
                return UserRole(local_role)
            except ValueError:
                pass
        normalized_roles = {role.strip().lower() for role in roles}
        if "admin" in normalized_roles:
            return UserRole.ADMIN
        if "customer" in normalized_roles:
            return UserRole.CUSTOMER
        if "public" in normalized_roles:
            return UserRole.PUBLIC
        return None

    def _as_string(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


def get_local_user_hydrator() -> LocalUserHydrator:
    return LocalUserHydrator()


def get_security_stamp_validator() -> SecurityStampValidator:
    return SecurityStampValidator()


def get_current_user_resolver(
    jwt_service: JWTService = Depends(get_jwt_service),
    local_user_hydrator: LocalUserHydrator = Depends(get_local_user_hydrator),
    security_stamp_validator: SecurityStampValidator = Depends(get_security_stamp_validator),
) -> CurrentUserResolver:
    return CurrentUserResolver(
        jwt_service=jwt_service,
        local_user_hydrator=local_user_hydrator,
        security_stamp_validator=security_stamp_validator,
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
    return resolver.resolve(
        token=credentials.credentials,
        db_session=db_session,
    )


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not current_user.has_role(UserRole.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ADMIN_ACCESS_REQUIRED,
        )
    return current_user
