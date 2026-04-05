from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.common.enums import SortOrder, UserRole
from app.common.security.password_service import PasswordService, get_password_service
from app.common.messages import (
    CUSTOMER_ID_REQUIRED,
    DATA_INTEGRITY_ERROR,
    MOBILE_ALREADY_EXISTS,
    CUSTOMER_ID_INVALID_OR_INACTIVE,
    ORGANIZATION_NAME_REQUIRED,
    ORGANIZATION_TYPE_REQUIRED,
    USER_NOT_FOUND,
)
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.users.dtos import UserCreate, UserUpdate
from app.modules.users.schemas import User


class UserQueryBuilder:
    SORT_COLUMNS = {
        "id": User.id,
        "full_name": User.full_name,
        "mobile": User.mobile,
        "role": User.role,
        "customer_id": User.customer_id,
        "is_active": User.is_active,
        "created_at": User.created_at,
        "updated_at": User.updated_at,
    }

    def build_list_query(
        self,
        role: UserRole | None,
        customer_id: int | None,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[User]]:
        query = select(User)
        if role is not None:
            query = query.where(User.role == role)
        if customer_id is not None:
            query = query.where(User.customer_id == customer_id)
        if is_active is None:
            query = query.where(User.is_active.is_(True))
        else:
            query = query.where(User.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.mobile.ilike(search_pattern),
                    User.organization_name.ilike(search_pattern),
                    User.organization_type.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), User.id.desc())
        else:
            query = query.order_by(sort_column.asc(), User.id.asc())
        return query


class UserRolePolicy:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def resolve_profile(
        self,
        *,
        role: UserRole,
        customer_id: int | None,
        organization_name: str | None,
        organization_type: str | None,
    ) -> tuple[int | None, str | None, str | None]:
        resolved_customer_id = self._resolve_customer_id(
            role=role,
            customer_id=customer_id,
        )
        resolved_organization_name, resolved_organization_type = self._resolve_organization_fields(
            role=role,
            organization_name=organization_name,
            organization_type=organization_type,
        )
        return (
            resolved_customer_id,
            resolved_organization_name,
            resolved_organization_type,
        )

    def _resolve_customer_id(
        self,
        *,
        role: UserRole,
        customer_id: int | None,
    ) -> int | None:
        if role in {UserRole.ADMIN, UserRole.PUBLIC}:
            return None
        if customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=CUSTOMER_ID_REQUIRED,
            )
        customer_table = Base.metadata.tables["customers"]
        customer = self._db_session.execute(
            select(customer_table.c.id).where(
                customer_table.c.id == customer_id,
                customer_table.c.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=CUSTOMER_ID_INVALID_OR_INACTIVE,
            )
        return customer_id

    def _resolve_organization_fields(
        self,
        *,
        role: UserRole,
        organization_name: str | None,
        organization_type: str | None,
    ) -> tuple[str | None, str | None]:
        if role != UserRole.PUBLIC:
            return None, None
        normalized_organization_name = organization_name.strip() if organization_name else None
        normalized_organization_type = organization_type.strip() if organization_type else None
        if not normalized_organization_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ORGANIZATION_NAME_REQUIRED,
            )
        if not normalized_organization_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ORGANIZATION_TYPE_REQUIRED,
            )
        return normalized_organization_name, normalized_organization_type


class UserService:
    def __init__(self, db_session: Session, password_service: PasswordService) -> None:
        self._db_session = db_session
        self._password_service = password_service
        self._query_builder = UserQueryBuilder()
        self._role_policy = UserRolePolicy(db_session=db_session)

    def create(self, dto: UserCreate) -> User:
        customer_id, organization_name, organization_type = self._role_policy.resolve_profile(
            role=dto.role,
            customer_id=dto.customer_id,
            organization_name=dto.organization_name,
            organization_type=dto.organization_type,
        )
        user = User(
            full_name=dto.full_name,
            mobile=dto.mobile,
            role=dto.role,
            customer_id=customer_id,
            organization_name=organization_name,
            organization_type=organization_type,
            password=self._hash_password(dto.password),
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
        customer_id: int | None,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[User], PaginationMeta]:
        query = self._query_builder.build_list_query(
            role=role,
            customer_id=customer_id,
            is_active=is_active,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total_count = int(
            self._db_session.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            ) or 0
        )
        paginated_query = query.offset(pagination.offset).limit(pagination.page_size)
        items = list(self._db_session.scalars(paginated_query).all())
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def get_or_404(self, user_id: int) -> User:
        user = self._db_session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=USER_NOT_FOUND,
            )
        return user

    def get_active_or_404(self, user_id: int) -> User:
        user = self.get_or_404(user_id=user_id)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=USER_NOT_FOUND,
            )
        return user

    def update(self, user_id: int, dto: UserUpdate) -> User:
        user = self.get_or_404(user_id=user_id)
        update_data = dto.model_dump(exclude_unset=True)
        password = self._extract_password_update(update_data)
        target_role = update_data.get("role", user.role)
        raw_customer_id = (
            update_data["customer_id"]
            if "customer_id" in update_data
            else user.customer_id
        )
        raw_organization_name = (
            update_data["organization_name"]
            if "organization_name" in update_data
            else user.organization_name
        )
        raw_organization_type = (
            update_data["organization_type"]
            if "organization_type" in update_data
            else user.organization_type
        )
        customer_id, organization_name, organization_type = self._role_policy.resolve_profile(
            role=target_role,
            customer_id=raw_customer_id,
            organization_name=raw_organization_name if raw_organization_name is None else str(raw_organization_name),
            organization_type=raw_organization_type if raw_organization_type is None else str(raw_organization_type),
        )
        for field_name, field_value in update_data.items():
            if field_name in {"customer_id", "organization_name", "organization_type", "password"}:
                continue
            setattr(user, field_name, field_value)
        user.role = target_role
        user.customer_id = customer_id
        user.organization_name = organization_name
        user.organization_type = organization_type
        if password is not None:
            user.password = password
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
                detail=MOBILE_ALREADY_EXISTS,
            )
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DATA_INTEGRITY_ERROR,
        )

    def _hash_password(self, password: str | None) -> str | None:
        if not password:
            return None
        return self._password_service.hash_password(password=password)

    def _extract_password_update(self, update_data: dict[str, object]) -> str | None:
        password = update_data.get("password")
        if not password:
            return None
        return self._password_service.hash_password(password=str(password))


def get_user_service(
    db_session: Session = Depends(get_db_session),
    password_service: PasswordService = Depends(get_password_service),
) -> UserService:
    return UserService(db_session=db_session, password_service=password_service)
