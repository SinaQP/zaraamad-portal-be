from fastapi import APIRouter, Depends, status

from app.common.dtos import CurrentUser
from app.common.security.dependencies import get_current_user
from app.modules.auth.dtos import (
    AccessTokenOut,
    AuthUserOut,
    LoginCreate,
    OtpRequestCreate,
    OtpRequestResult,
    PublicSignUpCreate,
    OtpVerifyCreate,
)
from app.modules.auth.mappers import AuthMapper, get_auth_mapper
from app.modules.auth.service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/sign-up",
    response_model=AccessTokenOut,
    status_code=status.HTTP_201_CREATED,
    summary="Public user sign up",
    description="Create a public user account and issue JWT access token.",
    responses={
        201: {"description": "Public user created and access token generated."},
        409: {"description": "Mobile number already exists."},
        422: {"description": "Validation failed."},
    },
)
def sign_up(
    payload: PublicSignUpCreate,
    service: AuthService = Depends(get_auth_service),
) -> AccessTokenOut:
    return service.sign_up_public(dto=payload)


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


@router.post(
    "/login",
    response_model=AccessTokenOut,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate user with mobile number and password, and issue JWT access token.",
    responses={
        200: {"description": "Access token generated successfully."},
        401: {"description": "Invalid mobile number or password, or user is inactive."},
    },
)
def login(
    payload: LoginCreate,
    service: AuthService = Depends(get_auth_service),
) -> AccessTokenOut:
    return service.login(dto=payload)


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
