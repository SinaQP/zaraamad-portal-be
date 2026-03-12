from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.enums import UserRole
from app.common.enums import SortOrder
from app.common.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.common.security.dependencies import require_admin
from app.modules.users.dtos import UserCreate, UserListOut, UserOut, UserUpdate
from app.modules.users.mappers import UserMapper, get_user_mapper
from app.modules.users.service import UserService, get_user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user with role admin or customer. Only admin users can access this endpoint.",
    responses={
        201: {"description": "User created."},
        403: {"description": "Admin access required."},
        409: {"description": "Mobile number already exists."},
        422: {"description": "Validation failed for role and customer relation."},
    },
)
def create_user(
    payload: UserCreate,
    _: object = Depends(require_admin),
    service: UserService = Depends(get_user_service),
    mapper: UserMapper = Depends(get_user_mapper),
) -> UserOut:
    user = service.create(dto=payload)
    return mapper.to_out(user=user)


@router.get(
    "",
    response_model=UserListOut,
    summary="List users",
    description="Return users with optional role, customer, and active-state filters.",
    responses={
        200: {"description": "User list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_users(
    response: Response,
    role: UserRole | None = Query(default=None, description="Filter by role."),
    customer_id: int | None = Query(default=None, description="Filter by customer id."),
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    search: str | None = Query(default=None, description="Search by user full name or mobile."),
    sort_by: Literal[
        "id",
        "full_name",
        "mobile",
        "role",
        "customer_id",
        "is_active",
        "created_at",
        "updated_at",
    ] = Query(default="id", description="Sort field."),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    _: object = Depends(require_admin),
    service: UserService = Depends(get_user_service),
    mapper: UserMapper = Depends(get_user_mapper),
) -> UserListOut:
    users, meta = service.list(
        role=role,
        customer_id=customer_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )
    set_pagination_headers(response=response, meta=meta)
    return UserListOut(
        items=[mapper.to_out(user=item) for item in users],
        total_page=meta.total_pages,
    )


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get user by id",
    description="Return a single user by id.",
    responses={
        200: {"description": "User returned."},
        403: {"description": "Admin access required."},
        404: {"description": "User not found."},
    },
)
def get_user(
    user_id: int,
    _: object = Depends(require_admin),
    service: UserService = Depends(get_user_service),
    mapper: UserMapper = Depends(get_user_mapper),
) -> UserOut:
    user = service.get_or_404(user_id=user_id)
    return mapper.to_out(user=user)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Update user",
    description="Partially update user data including role, customer assignment, and active status.",
    responses={
        200: {"description": "User updated."},
        403: {"description": "Admin access required."},
        404: {"description": "User not found."},
        409: {"description": "Data integrity error."},
        422: {"description": "Validation failed for role and customer relation."},
    },
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    _: object = Depends(require_admin),
    service: UserService = Depends(get_user_service),
    mapper: UserMapper = Depends(get_user_mapper),
) -> UserOut:
    user = service.update(user_id=user_id, dto=payload)
    return mapper.to_out(user=user)


@router.delete(
    "/{user_id}",
    response_model=UserOut,
    summary="Deactivate user",
    description="Soft delete user by setting is_active=false.",
    responses={
        200: {"description": "User deactivated."},
        403: {"description": "Admin access required."},
        404: {"description": "User not found."},
    },
)
def deactivate_user(
    user_id: int,
    _: object = Depends(require_admin),
    service: UserService = Depends(get_user_service),
    mapper: UserMapper = Depends(get_user_mapper),
) -> UserOut:
    user = service.deactivate(user_id=user_id)
    return mapper.to_out(user=user)
