from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.pagination import PaginatedResponse


class FeedbackCreate(MongoDTO):
    message: str | None = Field(
        default=None,
        max_length=5000,
        description="Optional long-form feedback message.",
        examples=["We need a simpler dashboard and faster support responses."],
    )
    selected_options: list[str] = Field(
        default_factory=list,
        description="Selected dynamic feedback labels from the UI buttons.",
        examples=[["Fast support", "Analytics", "Training"]],
    )

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("selected_options")
    @classmethod
    def normalize_selected_options(cls, value: list[str]) -> list[str]:
        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for raw_item in value:
            item = raw_item.strip()
            if not item:
                continue
            if len(item) > 255:
                raise ValueError("Each selected option must be at most 255 characters.")
            if item in seen_items:
                continue
            seen_items.add(item)
            normalized_items.append(item)
        return normalized_items

    @model_validator(mode="after")
    def validate_content(self) -> "FeedbackCreate":
        if self.message is None and not self.selected_options:
            raise ValueError("At least one of message or selected_options must be provided.")
        return self


class FeedbackOut(WithId):
    user_id: int = Field(..., description="Creator user id.", examples=[7])
    user_full_name: str = Field(..., description="Creator full name.", examples=["Sara Ahmadi"])
    user_mobile: str = Field(..., description="Creator mobile number.", examples=["09121112233"])
    message: str | None = Field(
        default=None,
        description="Long-form feedback message.",
        examples=["The reporting section should be easier to use."],
    )
    selected_options: list[str] = Field(
        ...,
        description="Selected feedback option labels.",
        examples=[["Fast support", "Analytics"]],
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class FeedbackListOut(PaginatedResponse[FeedbackOut]):
    pass
