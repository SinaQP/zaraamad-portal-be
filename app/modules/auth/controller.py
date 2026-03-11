from fastapi import APIRouter, Depends, status

from app.common.dtos import CurrentUser
from app.common.security.dependencies import get_current_user
from app.modules.auth.dtos import AccessTokenOut, AuthUserOut, OtpRequestCreate, OtpRequestResult, OtpVerifyCreate
from app.modules.auth.mappers import AuthMapper, get_auth_mapper
from app.modules.auth.service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/request-otp",
    response_model=OtpRequestResult,
    summary="Request OTP",
    description="Generate OTP for an existing active user. In development mode, OTP is returned in response.",
    responses={
        200: {"description": "OTP generated."},
        404: {"description": "User not found or inactive."},
        429: {"description": "Too many OTP requests."},
        500: {"description": "OTP delivery provider is not configured correctly."},
        503: {"description": "OTP delivery provider is unavailable."},
    },
)
def request_otp(
    payload: OtpRequestCreate,
    service: AuthService = Depends(get_auth_service),
) -> OtpRequestResult:
    return service.request_otp(dto=payload)


@router.post(
    "/verify-otp",
    response_model=AccessTokenOut,
    summary="Verify OTP",
    description="Verify OTP and issue JWT access token.",
    responses={
        200: {"description": "Access token generated."},
        400: {"description": "OTP is invalid or expired."},
        401: {"description": "User not found or inactive."},
    },
)
def verify_otp(
    payload: OtpVerifyCreate,
    service: AuthService = Depends(get_auth_service),
) -> AccessTokenOut:
    return service.verify_otp(dto=payload)


@router.get(
    "/me",
    response_model=AuthUserOut,
    summary="Get current user profile",
    description="Return current authenticated user profile.",
    responses={
        200: {"description": "Current user profile."},
        401: {"description": "Unauthorized."},
    },
)
def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    mapper: AuthMapper = Depends(get_auth_mapper),
) -> AuthUserOut:
    return mapper.from_current_user(current_user=current_user)
