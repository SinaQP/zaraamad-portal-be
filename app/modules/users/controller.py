from fastapi import APIRouter, Depends, Query, status

from app.common.enums import UserRole
from app.common.security.dependencies import require_admin
from app.modules.users.dtos import UserCreate, UserOut, UserUpdate
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
        422: {"description": "Validation failed for role and municipality relation."},
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
    response_model=list[UserOut],
    summary="List users",
    description="Return users with optional role, municipality, and active-state filters.",
    responses={
        200: {"description": "User list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_users(
    role: UserRole | None = Query(default=None, description="Filter by role."),
    municipality_id: int | None = Query(default=None, description="Filter by municipality id."),
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    _: object = Depends(require_admin),
    service: UserService = Depends(get_user_service),
    mapper: UserMapper = Depends(get_user_mapper),
) -> list[UserOut]:
    users = service.list(role=role, municipality_id=municipality_id, is_active=is_active)
    return [mapper.to_out(user=item) for item in users]


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
    description="Partially update user data including role, municipality assignment, and active status.",
    responses={
        200: {"description": "User updated."},
        403: {"description": "Admin access required."},
        404: {"description": "User not found."},
        409: {"description": "Data integrity error."},
        422: {"description": "Validation failed for role and municipality relation."},
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
