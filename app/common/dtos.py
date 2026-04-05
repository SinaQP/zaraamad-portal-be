from typing import Any

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
        description="JWT role claims as received from the token.",
        examples=[["Admin", "Operator"]],
    )
    security_stamp: str | None = Field(
        default=None,
        description="JWT security stamp claim when present.",
        examples=["stamp-123"],
    )
    raw_claims: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw verified JWT claims.",
    )
    id: int | None = Field(default=None, description="Local user id when mapped.", examples=[1])
    full_name: str | None = Field(
        default=None,
        description="Local user full name when mapped.",
        examples=["Admin"],
    )
    mobile: str | None = Field(
        default=None,
        description="Local user mobile when mapped.",
        examples=["09121234567"],
    )
    role: UserRole | None = Field(
        default=None,
        description="Resolved application role when available.",
        examples=[UserRole.ADMIN],
    )
    customer_id: int | None = Field(
        default=None,
        description="Local customer id if the user is mapped as a customer.",
        examples=[10],
    )
    is_active: bool | None = Field(
        default=None,
        description="Local user active status when mapped.",
        examples=[True],
    )

    def has_role(self, role_name: str) -> bool:
        normalized_target = role_name.strip().lower()
        normalized_roles = {role.strip().lower() for role in self.roles}
        if normalized_target in normalized_roles:
            return True
        if self.role is not None and self.role.value.lower() == normalized_target:
            return True
        return False

    def requires_local_user(self) -> bool:
        return self.id is not None


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
