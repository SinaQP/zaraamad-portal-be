from pydantic import Field, field_validator

from app.common.dtos import MongoDTO, WithId
from app.common.enums import UserRole
from app.common.validators.mobile_validator import get_mobile_validator


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


class AuthUserBase(MongoDTO):
    full_name: str = Field(..., description="User full name.", examples=["Ali Rezaei"])
    mobile: str = Field(..., description="Iranian mobile number.", examples=["09121234567"])
    role: UserRole = Field(..., description="User role.", examples=[UserRole.ADMIN])
    customer_id: int | None = Field(
        default=None,
        description="Customer id for customer users.",
        examples=[1],
    )
    is_active: bool = Field(..., description="User active status.", examples=[True])


class AuthUserOut(WithId, AuthUserBase):
    pass


class AccessTokenBase(MongoDTO):
    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field(..., description="Token type.", examples=["bearer"])
    user: AuthUserOut = Field(..., description="Authenticated user information.")


class AccessTokenOut(AccessTokenBase):
    pass
