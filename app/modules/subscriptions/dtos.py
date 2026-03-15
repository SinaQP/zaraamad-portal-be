from __future__ import annotations

from typing import Self

from pydantic import Field, field_validator, model_validator

from app.common.dtos import MongoDTO
from app.common.enums import SubscriptionMessageStatus
from app.common.validators.jalali_datetime import validate_jalali_datetime_string


class JalaliDateTimeFields(MongoDTO):
    @field_validator(
        "start_date",
        "end_date",
        "grace_period_end_date",
        check_fields=False,
    )
    @classmethod
    def validate_jalali_datetime(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_jalali_datetime_string(value)


class BridgeSubscriptionOut(JalaliDateTimeFields):
    start_date: str = Field(
        ...,
        description="Subscription start date as a Jalali datetime string.",
        examples=["1404-12-01 09:12:00"],
    )
    end_date: str = Field(
        ...,
        description="Subscription end date as a Jalali datetime string.",
        examples=["1405-03-01 00:00:00"],
    )
    grace_period_end_date: str | None = Field(
        default=None,
        description="Subscription grace-period end date as a Jalali datetime string.",
        examples=["1405-03-07 00:00:00"],
    )
    is_active: bool = Field(..., description="Whether the subscription is active.", examples=[True])
    status_message: str = Field(
        ...,
        description="Rendered subscription status message.",
        examples=[""],
    )


class BridgeSubscriptionUpdate(JalaliDateTimeFields):
    end_date: str | None = Field(
        default=None,
        description="Subscription end date as a Jalali datetime string.",
        examples=["1405-03-01 00:00:00"],
    )
    grace_period_end_date: str | None = Field(
        default=None,
        description="Subscription grace-period end date as a Jalali datetime string.",
        examples=["1405-03-07 00:00:00"],
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the subscription remains active.",
        examples=[True],
    )


class BridgeSubscriptionMessageBase(MongoDTO):
    status: SubscriptionMessageStatus = Field(
        ...,
        description="Subscription message status.",
        examples=[SubscriptionMessageStatus.EXPIRED],
    )
    message_template: str = Field(
        ...,
        description="Message template for the status. The template may include {days}.",
        examples=["اشتراک شما به پایان رسیده است."],
    )


class BridgeSubscriptionMessageUpdate(BridgeSubscriptionMessageBase):
    pass


class BridgeSubscriptionMessageOut(BridgeSubscriptionMessageBase):
    pass


class BridgeSubscriptionConfigOut(MongoDTO):
    subscription: BridgeSubscriptionOut = Field(..., description="Active subscription payload.")
    messages: list[BridgeSubscriptionMessageOut] = Field(
        ...,
        description="Configured subscription messages.",
    )


class BridgeSubscriptionConfigUpdate(MongoDTO):
    subscription: BridgeSubscriptionUpdate | None = Field(
        default=None,
        description="Partial active subscription update.",
    )
    messages: list[BridgeSubscriptionMessageUpdate] | None = Field(
        default=None,
        description="Message templates to create or update.",
    )

    @model_validator(mode="after")
    def validate_has_updates(self) -> Self:
        if self.subscription is None and self.messages is None:
            raise ValueError("At least one of subscription or messages must be provided.")
        return self
