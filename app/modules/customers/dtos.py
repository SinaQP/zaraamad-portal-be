from typing import Self

from datetime import datetime
import re

from pydantic import Field, field_validator, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.messages import ITEMS_MUST_NOT_BE_EMPTY
from app.common.pagination import PaginatedResponse
from app.common.validators.jalali_datetime import validate_jalali_datetime_string

CUSTOMER_INCOME_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class CustomerBridgeConfigNormalizer(MongoDTO):
    @field_validator("bridge_base_url", check_fields=False)
    @classmethod
    def normalize_bridge_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip().rstrip("/")
        return normalized_value or None

    @field_validator("bridge_api_key", check_fields=False)
    @classmethod
    def normalize_bridge_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None


class CustomerBase(MongoDTO):
    name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    manager_name: str | None = Field(
        default=None,
        description="Customer manager or contract signatory name.",
        examples=["Ali Rezaei"],
    )
    grade: int = Field(..., description="Customer grade.", examples=[1])


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(WithId, CustomerBase):
    is_active: bool = Field(..., description="Customer active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: str = Field(
        ...,
        description="Last update timestamp as a Jalali datetime string in YYYY-MM-DD HH:MM:SS format.",
        examples=["1405-01-05 14:35:22"],
    )

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: str) -> str:
        return validate_jalali_datetime_string(value)


class CustomerListOut(PaginatedResponse[CustomerOut]):
    pass


class CustomerIncomeMetricsBase(MongoDTO):
    registered_income_amount: int | None = Field(
        default=None,
        description="Registered income amount over the last 12 months.",
        examples=[1250000000],
    )
    issued_bill_count: int | None = Field(
        default=None,
        description="Issued bills count over the last 12 months.",
        examples=[3200],
    )
    paid_bill_count: int | None = Field(
        default=None,
        description="Paid bills count over the last 12 months.",
        examples=[2800],
    )
    collection_rate_percent: float | None = Field(
        default=None,
        description="Collection rate percentage over the last 12 months.",
        examples=[87.5],
    )


class CustomerIncomeSummaryOut(CustomerIncomeMetricsBase):
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class CustomerIncomeListCustomerOut(MongoDTO):
    id: int = Field(..., description="Customer id.", examples=[1])
    name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])


class CustomerIncomeListItemOut(MongoDTO):
    customer: CustomerIncomeListCustomerOut = Field(..., description="Customer information.")
    summary: CustomerIncomeSummaryOut = Field(..., description="Income summary for the customer.")


class CustomerIncomeListOut(PaginatedResponse[CustomerIncomeListItemOut]):
    pass


class CustomerIncomeBucketBase(MongoDTO):
    bucket_code: str = Field(..., description="Stable income bucket code.", examples=["110400"])
    bucket_name: str | None = Field(
        default=None,
        description="Display label for the income bucket.",
        examples=["Construction Fees"],
    )
    registered_income_amount: int | None = Field(
        default=None,
        description="Registered income amount for this bucket over the last 12 months.",
        examples=[420000000],
    )


class CustomerIncomeBucketOut(CustomerIncomeBucketBase):
    pass


class CustomerIncomeMonthlyReportBase(CustomerIncomeMetricsBase):
    month: str = Field(
        ...,
        description="Report month in YYYY-MM format.",
        examples=["2025-04"],
    )

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str) -> str:
        if not CUSTOMER_INCOME_MONTH_PATTERN.fullmatch(value):
            raise ValueError("Invalid customer income report month format. Use YYYY-MM.")
        return value


class CustomerIncomeMonthlyReportOut(CustomerIncomeMonthlyReportBase):
    pass


class CustomerIncomeCustomerOut(MongoDTO):
    id: int = Field(..., description="Customer id.", examples=[1])
    name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    manager_name: str | None = Field(
        default=None,
        description="Customer manager or contract signatory name.",
        examples=["Ali Rezaei"],
    )
    grade: int = Field(..., description="Customer grade.", examples=[1])


class CustomerIncomeDetailOut(MongoDTO):
    customer: CustomerIncomeCustomerOut = Field(..., description="Customer information.")
    summary: CustomerIncomeSummaryOut | None = Field(
        default=None,
        description="Income summary for the customer, or null if no income has been imported yet.",
    )
    buckets: list[CustomerIncomeBucketOut] = Field(
        ...,
        description="Income bucket breakdown for the customer.",
    )
    monthly_reports: list[CustomerIncomeMonthlyReportOut] = Field(
        ...,
        description="Monthly income report history for the customer.",
    )


class CustomerIncomeSummaryCreate(CustomerIncomeMetricsBase):
    pass


class CustomerIncomeBucketCreate(CustomerIncomeBucketBase):
    pass


class CustomerIncomeMonthlyReportCreate(CustomerIncomeMonthlyReportBase):
    pass


class CustomerIncomeBulkUpsertItemBase(MongoDTO):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    summary: CustomerIncomeSummaryCreate = Field(..., description="Income summary for the customer.")
    buckets: list[CustomerIncomeBucketCreate] = Field(
        ...,
        description="Income bucket breakdown for the customer.",
    )
    monthly_reports: list[CustomerIncomeMonthlyReportCreate] | None = Field(
        default=None,
        description="Optional monthly income report history for the customer.",
    )


class CustomerIncomeBulkUpsertItemCreate(CustomerIncomeBulkUpsertItemBase):
    pass


class CustomerIncomeBulkUpsertBase(MongoDTO):
    items: list[CustomerIncomeBulkUpsertItemCreate] = Field(
        ...,
        description="Bulk upsert items for customer income datasets.",
    )

    @model_validator(mode="after")
    def validate_non_empty_items(self) -> "CustomerIncomeBulkUpsertBase":
        if len(self.items) == 0:
            raise ValueError(ITEMS_MUST_NOT_BE_EMPTY)
        return self


class CustomerIncomeBulkUpsertCreate(CustomerIncomeBulkUpsertBase):
    pass


class CustomerUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Customer name.", examples=["Qom Customer"])
    manager_name: str | None = Field(
        default=None,
        description="Customer manager or contract signatory name.",
        examples=["Sara Ahmadi"],
    )
    grade: int | None = Field(default=None, description="Customer grade.", examples=[2])
    is_active: bool | None = Field(
        default=None,
        description="Customer active status.",
        examples=[True],
    )


class CustomerBridgeConfigUpdate(CustomerBridgeConfigNormalizer):
    bridge_base_url: str | None = Field(
        default=None,
        description="Customer bridge base URL.",
        examples=["https://tehran.example.com"],
    )
    bridge_api_key: str | None = Field(
        default=None,
        description="Shared secret used for bridge requests.",
        examples=["bridge-secret"],
    )
    bridge_is_enabled: bool | None = Field(
        default=None,
        description="Whether customer bridge access is enabled.",
        examples=[True],
    )

    @model_validator(mode="after")
    def validate_has_updates(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one bridge configuration field must be provided.")
        return self


class CustomerBridgeConfigOut(MongoDTO):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    customer_name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    bridge_base_url: str | None = Field(
        default=None,
        description="Configured bridge base URL for this customer.",
        examples=["https://tehran.example.com"],
    )
    bridge_is_enabled: bool = Field(
        ...,
        description="Whether bridge access is enabled for this customer.",
        examples=[True],
    )
    bridge_has_api_key: bool = Field(
        ...,
        description="Whether the customer bridge API key is configured.",
        examples=[True],
    )
    last_online_status: bool | None = Field(
        default=None,
        description="Most recently cached online status for this customer bridge.",
        examples=[True],
    )
    last_health_checked_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recent cached bridge health check.",
    )
    last_health_error: str | None = Field(
        default=None,
        description="Last cached bridge health error when the bridge was not reachable or returned an invalid response.",
        examples=["timed out"],
    )


class CustomerBridgeHealthBase(MongoDTO):
    status: str = Field(..., description="Bridge health status.", examples=["ok"])
    bridge_name: str = Field(..., description="Bridge display name.", examples=["Tehran Support Bridge"])
    bridge_version: str | None = Field(
        default=None,
        description="Bridge version reported by the municipality bridge.",
        examples=["1.0.0"],
    )


class CustomerBridgeHealthOut(CustomerBridgeHealthBase):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    customer_name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    bridge_base_url: str = Field(
        ...,
        description="Bridge base URL used for the health request.",
        examples=["https://tehran.example.com"],
    )


class CustomerBridgeCapabilityBase(MongoDTO):
    code: str = Field(..., description="Capability code.", examples=["support.health.read"])
    name: str = Field(..., description="Capability display name.", examples=["Read bridge health"])
    description: str | None = Field(
        default=None,
        description="Capability description.",
        examples=["Allows support portal health probes."],
    )


class CustomerBridgeCapabilitiesOut(MongoDTO):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    customer_name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    bridge_base_url: str = Field(
        ...,
        description="Bridge base URL used for the capabilities request.",
        examples=["https://tehran.example.com"],
    )
    bridge_name: str = Field(..., description="Bridge display name.", examples=["Tehran Support Bridge"])
    bridge_version: str | None = Field(
        default=None,
        description="Bridge version reported by the municipality bridge.",
        examples=["1.0.0"],
    )
    capabilities: list[CustomerBridgeCapabilityBase] = Field(
        ...,
        description="Supported bridge capabilities.",
    )


class CustomerBridgeSubscriptionBase(MongoDTO):
    start_date: str = Field(
        ...,
        description="Subscription start date as a Jalali datetime string.",
        examples=["1405-01-01 00:00:00"],
    )
    end_date: str = Field(
        ...,
        description="Subscription end date as a Jalali datetime string.",
        examples=["1405-02-01 00:00:00"],
    )
    grace_period_end_date: str | None = Field(
        default=None,
        description="Subscription grace-period end date as a Jalali datetime string.",
        examples=["1405-02-10 00:00:00"],
    )
    is_active: bool = Field(
        ...,
        description="Whether the upstream subscription is active.",
        examples=[True],
    )
    status_message: str = Field(
        ...,
        description="Rendered subscription status message returned by the main app.",
        examples=[""],
    )
    last_subscription_synced_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recent successful or definitive subscription refresh.",
    )
    last_subscription_error: str | None = Field(
        default=None,
        description="Last cached subscription refresh error for this customer bridge.",
        examples=["No active subscription exists."],
    )


class CustomerBridgeSubscriptionOut(CustomerBridgeSubscriptionBase):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    customer_name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    bridge_base_url: str = Field(
        ...,
        description="Bridge base URL used for the subscription request.",
        examples=["https://tehran.example.com"],
    )
