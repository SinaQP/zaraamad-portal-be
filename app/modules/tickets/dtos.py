from datetime import datetime

from pydantic import Field, field_validator

from app.common.dtos import MongoDTO, WithId
from app.common.pagination import PaginatedResponse
from app.modules.tickets.constants import TicketPriority, TicketStatus


class TicketBase(MongoDTO):
    title: str = Field(..., min_length=1, max_length=255, description="Ticket title.", examples=["اتصال سامانه قطع می‌شود"])
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Detailed ticket description.",
        examples=["بعد از ورود به پنل، صفحه گزارش‌ها باز نمی‌شود."],
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        description="Ticket priority level.",
        examples=[TicketPriority.MEDIUM],
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TicketCreate(TicketBase):
    assigned_to_user_id: int | None = Field(
        default=None,
        description="Optional assignee user id.",
        examples=[12],
    )


class TicketOut(WithId, TicketBase):
    status: TicketStatus = Field(..., description="Ticket lifecycle status.", examples=[TicketStatus.OPEN])
    created_by_user_id: int = Field(..., description="Creator user id.", examples=[7])
    assigned_to_user_id: int | None = Field(default=None, description="Assignee user id.", examples=[12])
    status_changed_by_user_id: int | None = Field(
        default=None,
        description="User id that last changed the status.",
        examples=[1],
    )
    resolved_at: datetime | None = Field(default=None, description="Resolution timestamp when applicable.")
    is_active: bool = Field(..., description="Soft-delete active flag.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class TicketListOut(PaginatedResponse[TicketOut]):
    pass


class TicketUpdate(MongoDTO):
    title: str | None = Field(default=None, min_length=1, max_length=255, description="Updated ticket title.")
    description: str | None = Field(default=None, max_length=5000, description="Updated ticket description.")
    priority: TicketPriority | None = Field(default=None, description="Updated priority.")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TicketStatusUpdate(MongoDTO):
    status: TicketStatus = Field(..., description="Target ticket status.", examples=[TicketStatus.IN_PROGRESS])


class TicketAssignRequest(MongoDTO):
    assigned_to_user_id: int | None = Field(
        default=None,
        description="Assignee user id. Use null to clear assignment.",
        examples=[10],
    )

