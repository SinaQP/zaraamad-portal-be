from app.common.dtos import CurrentUser
from app.modules.auth.dtos import AuthUserOut


class AuthMapper:
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
