from collections.abc import Mapping
from typing import Any

from app.common.dtos import CurrentUser
from app.modules.auth.dtos import AuthUserOut, AuthenticatedUserOut
from app.modules.users.schemas import User


class AuthMapper:
    def from_user_row(self, user_row: Mapping[str, Any]) -> AuthenticatedUserOut:
        return AuthenticatedUserOut(
            id=user_row["id"],
            full_name=user_row["full_name"],
            mobile=user_row["mobile"],
            role=user_row["role"],
            customer_id=user_row["customer_id"],
            organization_name=user_row["organization_name"],
            organization_type=user_row["organization_type"],
            is_active=user_row["is_active"],
        )

    def from_user(self, user: User) -> AuthenticatedUserOut:
        return AuthenticatedUserOut(
            id=user.id,
            full_name=user.full_name,
            mobile=user.mobile,
            role=user.role,
            customer_id=user.customer_id,
            organization_name=user.organization_name,
            organization_type=user.organization_type,
            is_active=user.is_active,
        )

    def from_current_user(self, current_user: CurrentUser) -> AuthUserOut:
        return AuthUserOut(
            user_id=current_user.user_id,
            sub=current_user.sub,
            roles=list(current_user.roles),
            security_stamp=current_user.security_stamp,
            raw_claims=current_user.raw_claims,
        )


def get_auth_mapper() -> AuthMapper:
    return AuthMapper()
