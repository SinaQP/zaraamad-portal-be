from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common import model_registry as _model_registry
from app.common.config import Settings
from app.common.enums import UserRole
from app.common.validators.mobile_validator import get_mobile_validator
from app.modules.users.schemas import User


class AdminSeedService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mobile_validator = get_mobile_validator()

    def seed_default_admin(self, db_session: Session) -> User:
        mobile = self._mobile_validator.normalize(self._settings.seed_admin_mobile)
        existing_user = db_session.execute(
            select(User).where(User.mobile == mobile)
        ).scalar_one_or_none()
        if existing_user is not None:
            return existing_user
        admin = User(
            full_name=self._settings.seed_admin_full_name,
            mobile=mobile,
            role=UserRole.ADMIN,
            municipality_id=None,
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
        return admin
