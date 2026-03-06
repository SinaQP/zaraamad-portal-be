from pydantic import BaseModel, ConfigDict, Field


class MongoDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


class WithId(MongoDTO):
    id: str = Field(
        ...,
        description="Unique identifier.",
        examples=["65f1b9ac8e6ec7d24b4f6f2a"],
    )
