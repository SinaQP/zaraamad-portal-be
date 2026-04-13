from app.common.dtos import MongoDTO
from pydantic import Field


class HealthDependencyOut(MongoDTO):
    name: str = Field(
        ...,
        description="Dependency name.",
        examples=["postgres"],
    )
    is_online: bool = Field(
        ...,
        description="Whether the dependency is reachable.",
        examples=[True],
    )
    status: str = Field(
        ...,
        description="Resolved dependency status.",
        examples=["online"],
    )
    detail: str = Field(
        ...,
        description="Human-readable health detail.",
        examples=["اتصال به پایگاه داده اصلی برقرار است."],
    )


class HealthStatusOut(MongoDTO):
    status: str = Field(
        ...,
        description="Overall health status.",
        examples=["online"],
    )
    dependencies: list[HealthDependencyOut] = Field(
        default_factory=list,
        description="Dependency health results.",
    )
