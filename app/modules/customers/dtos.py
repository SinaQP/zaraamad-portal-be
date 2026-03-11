from datetime import datetime

from pydantic import Field

from app.common.dtos import MongoDTO, WithId


class CustomerBase(MongoDTO):
    name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    grade: int = Field(..., description="Customer grade.", examples=[1])


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(WithId, CustomerBase):
    is_active: bool = Field(..., description="Customer active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class CustomerUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Customer name.", examples=["Qom Customer"])
    grade: int | None = Field(default=None, description="Customer grade.", examples=[2])
    is_active: bool | None = Field(
        default=None,
        description="Customer active status.",
        examples=[True],
    )
