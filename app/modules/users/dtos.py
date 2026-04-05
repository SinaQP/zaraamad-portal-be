from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.enums import UserRole
from app.common.messages import (
    CUSTOMER_ID_REQUIRED,
    ORGANIZATION_NAME_REQUIRED,
    ORGANIZATION_TYPE_REQUIRED,
)
from app.common.pagination import PaginatedResponse
from app.common.validators.mobile_validator import get_mobile_validator


class UserPayloadBase(MongoDTO):
    full_name: str = Field(..., description="User full name.", examples=["Ali Rezaei"])
    mobile: str = Field(..., description="Iranian mobile number.", examples=["09121234567"])
    role: UserRole = Field(..., description="User role.", examples=[UserRole.CUSTOMER])
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

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        return get_mobile_validator().normalize(value)

    @model_validator(mode="after")
    def validate_role_constraints(self) -> "UserPayloadBase":
        if self.role == UserRole.CUSTOMER and self.customer_id is None:
            raise ValueError(CUSTOMER_ID_REQUIRED)
        if self.role == UserRole.PUBLIC and not self.organization_name:
            raise ValueError(ORGANIZATION_NAME_REQUIRED)
        if self.role == UserRole.PUBLIC and not self.organization_type:
            raise ValueError(ORGANIZATION_TYPE_REQUIRED)
        if self.role in {UserRole.ADMIN, UserRole.PUBLIC}:
            self.customer_id = None
        if self.role != UserRole.PUBLIC:
            self.organization_name = None
            self.organization_type = None
        return self


class UserCreate(UserPayloadBase):
    password: str | None = Field(default=None, description="User password.", examples=["your_secure_password"])

    @field_validator("password")
    @classmethod
    def normalize_password(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value


class UserOut(WithId, UserPayloadBase):
    is_active: bool = Field(..., description="User active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class UserListOut(PaginatedResponse[UserOut]):
    pass


class UserUpdate(MongoDTO):
    full_name: str | None = Field(default=None, description="User full name.", examples=["Sara Ahmadi"])
    mobile: str | None = Field(default=None, description="Iranian mobile number.", examples=["09125556677"])
    password: str | None = Field(default=None, description="User password.", examples=["1234"])
    role: UserRole | None = Field(default=None, description="User role.", examples=[UserRole.ADMIN])
    customer_id: int | None = Field(
        default=None,
        description="Customer id for customer users.",
        examples=[2],
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
    is_active: bool | None = Field(default=None, description="User active status.", examples=[True])

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return get_mobile_validator().normalize(value)

    @field_validator("password")
    @classmethod
    def normalize_password(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value
