from datetime import datetime

from pydantic import Field

from app.common.dtos import MongoDTO, WithId


class MunicipalityBase(MongoDTO):
    name: str = Field(..., description="Municipality name.", examples=["Tehran Municipality"])
    grade: int = Field(..., description="Municipality grade.", examples=[1])


class MunicipalityCreate(MunicipalityBase):
    pass


class MunicipalityOut(WithId, MunicipalityBase):
    is_active: bool = Field(..., description="Municipality active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class MunicipalityUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Municipality name.", examples=["Qom Municipality"])
    grade: int | None = Field(default=None, description="Municipality grade.", examples=[2])
    is_active: bool | None = Field(
        default=None,
        description="Municipality active status.",
        examples=[True],
    )
