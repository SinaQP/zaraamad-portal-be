from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.enums import UserRole
from app.common.messages import CUSTOMER_ID_REQUIRED
from app.common.pagination import PaginatedResponse
from app.common.validators.mobile_validator import get_mobile_validator


class UserBase(MongoDTO):
    full_name: str = Field(..., description="User full name.", examples=["Ali Rezaei"])
    mobile: str = Field(..., description="Iranian mobile number.", examples=["09121234567"])
    role: UserRole = Field(..., description="User role.", examples=[UserRole.CUSTOMER])
    customer_id: int | None = Field(
        default=None,
        description="Customer id for customer users.",
        examples=[1],
    )

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        return get_mobile_validator().normalize(value)

    @model_validator(mode="after")
    def validate_role_constraints(self) -> "UserBase":
        if self.role == UserRole.CUSTOMER and self.customer_id is None:
            raise ValueError(CUSTOMER_ID_REQUIRED)
        if self.role == UserRole.ADMIN:
            self.customer_id = None
        return self


class UserCreate(UserBase):
    pass


class UserOut(WithId, UserBase):
    is_active: bool = Field(..., description="User active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class UserListOut(PaginatedResponse[UserOut]):
    pass


class UserUpdate(MongoDTO):
    full_name: str | None = Field(default=None, description="User full name.", examples=["Sara Ahmadi"])
    mobile: str | None = Field(default=None, description="Iranian mobile number.", examples=["09125556677"])
    role: UserRole | None = Field(default=None, description="User role.", examples=[UserRole.ADMIN])
    customer_id: int | None = Field(
        default=None,
        description="Customer id for customer users.",
        examples=[2],
    )
    is_active: bool | None = Field(default=None, description="User active status.", examples=[True])

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return get_mobile_validator().normalize(value)
