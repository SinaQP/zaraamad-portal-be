from fastapi import APIRouter, Depends

from app.common.dtos import CurrentUser
from app.common.security.dependencies import get_current_user
from app.modules.auth.dtos import AuthUserOut
from app.modules.auth.mappers import AuthMapper, get_auth_mapper

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    response_model=AuthUserOut,
    summary="Get current user from JWT",
    description="Validate the bearer token and return the resolved current-user context.",
    responses={
        200: {"description": "Current authenticated user context."},
        401: {"description": "Unauthorized."},
    },
)
def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    mapper: AuthMapper = Depends(get_auth_mapper),
) -> AuthUserOut:
    return mapper.from_current_user(current_user=current_user)
