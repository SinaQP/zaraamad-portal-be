from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import UserRole


class MongoDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


class WithId(MongoDTO):
    id: int = Field(
        ...,
        description="Unique identifier.",
        examples=[1],
    )


class CurrentUser(MongoDTO):
    id: int = Field(..., description="Current user id.", examples=[1])
    full_name: str = Field(..., description="Current user full name.", examples=["Admin"])
    mobile: str = Field(..., description="Current user mobile.", examples=["09121234567"])
    role: UserRole = Field(..., description="Current user role.", examples=[UserRole.ADMIN])
    municipality_id: int | None = Field(
        default=None,
        description="Current user municipality id if role is customer.",
        examples=[10],
    )
    is_active: bool = Field(..., description="Current user active status.", examples=[True])


class HomePageOut(MongoDTO):
    message: str = Field(
        ...,
        description="Welcome message for API root.",
        examples=["Welcome to Zaraamad Portal API"],
    )
    app_name: str = Field(
        ...,
        description="Application name.",
        examples=["Zaraamad Portal API"],
    )
    version: str = Field(
        ...,
        description="Application version.",
        examples=["1.0.0"],
    )
    docs_url: str = Field(
        ...,
        description="Swagger documentation URL.",
        examples=["/docs"],
    )
    redoc_url: str = Field(
        ...,
        description="ReDoc documentation URL.",
        examples=["/redoc"],
    )
