from app.modules.users.dtos import UserOut
from app.modules.users.schemas import User


class UserMapper:
    def to_out(self, user: User) -> UserOut:
        return UserOut(
            id=user.id,
            full_name=user.full_name,
            mobile=user.mobile,
            role=user.role,
            customer_id=user.customer_id,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            password=user.password
        )


def get_user_mapper() -> UserMapper:
    return UserMapper()
