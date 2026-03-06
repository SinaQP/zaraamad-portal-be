from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.common.enums import UserRole
from app.modules.users.dtos import UserCreate, UserUpdate
from app.modules.users.schemas import User


class UserQueryBuilder:
    def build_list_query(
        self,
        role: UserRole | None,
        municipality_id: int | None,
        is_active: bool | None,
    ) -> Select[tuple[User]]:
        query = select(User).order_by(User.id.asc())
        if role is not None:
            query = query.where(User.role == role)
        if municipality_id is not None:
            query = query.where(User.municipality_id == municipality_id)
        if is_active is not None:
            query = query.where(User.is_active.is_(is_active))
        return query


class UserRolePolicy:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def resolve_municipality_id(
        self,
        role: UserRole,
        municipality_id: int | None,
    ) -> int | None:
        if role == UserRole.ADMIN:
            return None
        if municipality_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="municipality_id is required for customer users.",
            )
        municipality_table = Base.metadata.tables["municipalities"]
        municipality = self._db_session.execute(
            select(municipality_table.c.id).where(
                municipality_table.c.id == municipality_id,
                municipality_table.c.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if municipality is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="municipality_id is invalid or inactive.",
            )
        return municipality_id


class UserService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = UserQueryBuilder()
        self._role_policy = UserRolePolicy(db_session=db_session)

    def create(self, dto: UserCreate) -> User:
        municipality_id = self._role_policy.resolve_municipality_id(
            role=dto.role,
            municipality_id=dto.municipality_id,
        )
        user = User(
            full_name=dto.full_name,
            mobile=dto.mobile,
            email=dto.email,
            role=dto.role,
            municipality_id=municipality_id,
            is_active=True,
        )
        self._db_session.add(user)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise self._integrity_exception(exc)
        self._db_session.refresh(user)
        return user

    def list(
        self,
        role: UserRole | None,
        municipality_id: int | None,
        is_active: bool | None,
    ) -> list[User]:
        query = self._query_builder.build_list_query(
            role=role,
            municipality_id=municipality_id,
            is_active=is_active,
        )
        return list(self._db_session.scalars(query).all())

    def get_or_404(self, user_id: int) -> User:
        user = self._db_session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        return user

    def update(self, user_id: int, dto: UserUpdate) -> User:
        user = self.get_or_404(user_id=user_id)
        update_data = dto.model_dump(exclude_unset=True)
        target_role = update_data.get("role", user.role)
        raw_municipality_id = (
            update_data["municipality_id"]
            if "municipality_id" in update_data
            else user.municipality_id
        )
        municipality_id = self._role_policy.resolve_municipality_id(
            role=target_role,
            municipality_id=raw_municipality_id,
        )
        for field_name, field_value in update_data.items():
            if field_name == "municipality_id":
                continue
            setattr(user, field_name, field_value)
        user.role = target_role
        user.municipality_id = municipality_id
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise self._integrity_exception(exc)
        self._db_session.refresh(user)
        return user

    def deactivate(self, user_id: int) -> User:
        user = self.get_or_404(user_id=user_id)
        user.is_active = False
        self._db_session.commit()
        self._db_session.refresh(user)
        return user

    def _integrity_exception(self, exc: IntegrityError) -> HTTPException:
        error_text = str(exc.orig).lower()
        if "mobile" in error_text:
            return HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mobile number already exists.",
            )
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data integrity error.",
        )


def get_user_service(db_session: Session = Depends(get_db_session)) -> UserService:
    return UserService(db_session=db_session)
