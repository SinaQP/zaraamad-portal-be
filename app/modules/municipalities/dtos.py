from datetime import datetime

from pydantic import Field

from app.common.dtos import MongoDTO, WithId


class MunicipalityBase(MongoDTO):
    name: str = Field(..., description="Municipality name.", examples=["Tehran Municipality"])
    code: str = Field(..., description="Unique municipality code.", examples=["THR-001"])
    province: str | None = Field(
        default=None,
        description="Province name.",
        examples=["Tehran"],
    )
    city: str | None = Field(
        default=None,
        description="City name.",
        examples=["Tehran"],
    )


class MunicipalityCreate(MunicipalityBase):
    pass


class MunicipalityOut(WithId, MunicipalityBase):
    is_active: bool = Field(..., description="Municipality active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class MunicipalityUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Municipality name.", examples=["Qom Municipality"])
    code: str | None = Field(default=None, description="Municipality code.", examples=["QOM-001"])
    province: str | None = Field(default=None, description="Province name.", examples=["Qom"])
    city: str | None = Field(default=None, description="City name.", examples=["Qom"])
    is_active: bool | None = Field(
        default=None,
        description="Municipality active status.",
        examples=[True],
    )
