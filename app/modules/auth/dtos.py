from typing import Any

from pydantic import Field, field_validator

from app.common.dtos import MongoDTO, WithId
from app.common.enums import UserRole
from app.common.validators.mobile_validator import get_mobile_validator


class AuthUserOut(MongoDTO):
    user_id: str = Field(
        ...,
        description="Resolved identity from JWT sub or user_id claim.",
        examples=["11111111-1111-1111-1111-111111111111"],
    )
    sub: str | None = Field(
        default=None,
        description="JWT sub claim when present.",
        examples=["11111111-1111-1111-1111-111111111111"],
    )
    roles: list[str] = Field(
        default_factory=list,
        description="JWT role claims.",
        examples=[["Admin", "Operator"]],
    )
    security_stamp: str | None = Field(
        default=None,
        description="JWT security stamp claim.",
        examples=["stamp-123"],
    )
    raw_claims: dict[str, Any] = Field(
        default_factory=dict,
        description="Full verified JWT payload.",
    )


class OtpRequestBase(MongoDTO):
    mobile: str = Field(..., description="Iranian mobile number.", examples=["09121234567"])

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        return get_mobile_validator().normalize(value)


class OtpRequestCreate(OtpRequestBase):
    pass


class OtpRequestResult(MongoDTO):
    message: str = Field(..., description="Operation result message.", examples=["OTP generated."])
    dev_otp: str | None = Field(
        default=None,
        description="OTP value in development mode only.",
        examples=["123456"],
    )


class OtpVerifyBase(MongoDTO):
    mobile: str = Field(..., description="Iranian mobile number.", examples=["09121234567"])
    otp_code: str = Field(..., description="One-time password code.", examples=["123456"])

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        return get_mobile_validator().normalize(value)


class OtpVerifyCreate(OtpVerifyBase):
    pass


class PublicSignUpCreate(OtpRequestBase):
    full_name: str = Field(..., min_length=1, description="User full name.", examples=["Ali Rezaei"])
    organization_name: str = Field(
        ...,
        min_length=1,
        description="Organization name.",
        examples=["Tehran Tech Association"],
    )
    organization_type: str = Field(
        ...,
        min_length=1,
        description="Organization type.",
        examples=["private"],
    )


class AuthenticatedUserOut(WithId):
    full_name: str = Field(..., description="User full name.", examples=["Ali Rezaei"])
    mobile: str = Field(..., description="Iranian mobile number.", examples=["09121234567"])
    role: UserRole = Field(..., description="User role.", examples=[UserRole.ADMIN])
    customer_id: int | None = Field(
        default=None,
        description="Customer id for customer users.",
        examples=[1],
    )
    organization_name: str | None = Field(
        default=None,
        description="Organization name for public users.",
        examples=["Tehran Tech Association"],
    )
    organization_type: str | None = Field(
        default=None,
        description="Organization type for public users.",
        examples=["private"],
    )
    is_active: bool = Field(..., description="User active status.", examples=[True])


class AccessTokenOut(MongoDTO):
    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field(..., description="Token type.", examples=["bearer"])
    user: AuthenticatedUserOut = Field(..., description="Authenticated user information.")


class LoginCreate(MongoDTO):
    mobile: str = Field(..., description="User mobile number.", examples=["09121234567"])
    password: str = Field(..., description="User password.", examples=["your_secure_password"])

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        return get_mobile_validator().normalize(value)
