from datetime import date, datetime

from pydantic import Field

from app.common.dtos import MongoDTO, WithId
from app.common.enums import SubscriptionMessageStatus


class SubscriptionBase(MongoDTO):
    start_date: date = Field(..., description="Subscription start date.", examples=["2026-03-12"])
    end_date: date = Field(..., description="Subscription end date.", examples=["2026-04-12"])
    grace_period_end_date: date | None = Field(
        default=None,
        description="Grace period end date.",
        examples=["2026-04-20"],
    )
    is_active: bool = Field(..., description="Whether this subscription is active.", examples=[True])


class SubscriptionCreateBase(MongoDTO):
    end_date: date = Field(..., description="Subscription end date.", examples=["2026-04-12"])


class SubscriptionCreate(SubscriptionCreateBase):
    pass


class SubscriptionOut(WithId, SubscriptionBase):
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class SubscriptionUpdate(MongoDTO):
    end_date: date | None = Field(default=None, description="Subscription end date.", examples=["2026-04-15"])
    grace_period_end_date: date | None = Field(
        default=None,
        description="Grace period end date.",
        examples=["2026-04-25"],
    )
    is_active: bool | None = Field(default=None, description="Whether the subscription remains active.", examples=[True])


class SubscriptionMessageBase(MongoDTO):
    status: SubscriptionMessageStatus = Field(
        ...,
        description="Subscription message status.",
        examples=[SubscriptionMessageStatus.EXPIRED],
    )
    message_template: str = Field(
        ...,
        description="Message template for the status. The template may include {days}.",
        examples=["اشتراک شما {days} روز پیش منقضی شده است."],
    )


class SubscriptionMessageCreate(SubscriptionMessageBase):
    pass


class SubscriptionMessageOut(WithId, SubscriptionMessageBase):
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")
