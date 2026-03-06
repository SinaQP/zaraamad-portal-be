from collections.abc import Mapping
from typing import Any

from app.common.dtos import CurrentUser
from app.modules.auth.dtos import AuthUserOut


class AuthMapper:
    def from_user_row(self, user_row: Mapping[str, Any]) -> AuthUserOut:
        return AuthUserOut(
            id=user_row["id"],
            full_name=user_row["full_name"],
            mobile=user_row["mobile"],
            email=user_row["email"],
            role=user_row["role"],
            municipality_id=user_row["municipality_id"],
            is_active=user_row["is_active"],
        )

    def from_current_user(self, current_user: CurrentUser) -> AuthUserOut:
        return AuthUserOut(
            id=current_user.id,
            full_name=current_user.full_name,
            mobile=current_user.mobile,
            email=current_user.email,
            role=current_user.role,
            municipality_id=current_user.municipality_id,
            is_active=current_user.is_active,
        )


def get_auth_mapper() -> AuthMapper:
    return AuthMapper()
