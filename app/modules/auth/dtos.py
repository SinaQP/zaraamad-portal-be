from typing import Any

from pydantic import Field

from app.common.dtos import MongoDTO


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
