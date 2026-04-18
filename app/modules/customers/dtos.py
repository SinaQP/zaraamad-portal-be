from typing import Self

from datetime import datetime
import re

from pydantic import AliasChoices, Field, field_validator, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.messages import ITEMS_MUST_NOT_BE_EMPTY
from app.common.pagination import PaginatedResponse
from app.common.validators.jalali_datetime import validate_jalali_datetime_string

CUSTOMER_INCOME_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class CustomerBridgeConfigNormalizer(MongoDTO):
    @field_validator("base_url_internal", "bridge_base_url", check_fields=False)
    @classmethod
    def normalize_bridge_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip().rstrip("/")
        return normalized_value or None

    @field_validator(
        "bridge_api_key",
        "instance_id",
        "audience",
        "tenant_id",
        check_fields=False,
    )
    @classmethod
    def normalize_bridge_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("status", check_fields=False)
    @classmethod
    def normalize_bridge_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip().lower()
        return normalized_value or None


class CustomerDatabaseConnectionNormalizer(MongoDTO):
    @field_validator(
        "connection_string",
        "secret_version",
        check_fields=False,
    )
    @classmethod
    def normalize_database_connection_text(cls, value: str | None) -> str | None:
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
    instance_id: str | None = Field(
        default=None,
        description="Bridge instance identifier for this customer.",
        examples=["default", "tehran-prod"],
    )
    base_url_internal: str | None = Field(
        default=None,
        validation_alias=AliasChoices("base_url_internal", "bridge_base_url"),
        description="Internal base URL for routing Portal requests to Zaraamad.",
        examples=["https://tehran.example.com"],
    )
    bridge_api_key: str | None = Field(
        default=None,
        description="Legacy bridge API key (optional transitional fallback).",
        examples=["bridge-secret"],
    )
    audience: str | None = Field(
        default=None,
        description="Audience claim expected by the target Zaraamad instance.",
        examples=["zaraamad:tehran-prod"],
    )
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier claim to send for the target instance.",
        examples=["tehran"],
    )
    status: str | None = Field(
        default=None,
        description="Bridge routing/auth status. Use 'active' to allow outbound traffic.",
        examples=["active", "inactive"],
    )
    bridge_is_enabled: bool | None = Field(
        default=None,
        description="Legacy alias for status. true => active, false => inactive.",
        examples=[True],
    )
    request_timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        description="Optional per-instance request timeout override in seconds.",
        examples=[10],
    )
    request_retry_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional retry count for transient upstream connectivity errors.",
        examples=[1],
    )
    request_retry_backoff_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Optional retry backoff between attempts in seconds.",
        examples=[0.25],
    )

    @model_validator(mode="after")
    def normalize_legacy_status_alias(self) -> Self:
        if self.bridge_is_enabled is None:
            return self
        legacy_status = "active" if self.bridge_is_enabled else "inactive"
        if self.status is not None and self.status != legacy_status:
            raise ValueError("status and bridge_is_enabled conflict.")
        self.status = legacy_status
        return self

    @model_validator(mode="after")
    def validate_has_updates(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one bridge configuration field must be provided.")
        return self


class CustomerBridgeConfigOut(MongoDTO):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    customer_name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    instance_id: str = Field(
        ...,
        description="Bridge instance identifier.",
        examples=["default"],
    )
    base_url_internal: str | None = Field(
        default=None,
        description="Configured internal target base URL for this customer instance.",
        examples=["https://tehran.example.com"],
    )
    audience: str | None = Field(
        default=None,
        description="Configured audience claim for this instance.",
        examples=["zaraamad:tehran-prod"],
    )
    tenant_id: str | None = Field(
        default=None,
        description="Configured tenant identifier for this instance.",
        examples=["tehran"],
    )
    status: str = Field(
        ...,
        description="Current bridge instance status.",
        examples=["active"],
    )
    request_timeout_seconds: int | None = Field(
        default=None,
        description="Optional per-instance timeout override in seconds.",
        examples=[10],
    )
    request_retry_count: int | None = Field(
        default=None,
        description="Optional retry count for transient connectivity failures.",
        examples=[1],
    )
    request_retry_backoff_seconds: float | None = Field(
        default=None,
        description="Optional retry backoff in seconds.",
        examples=[0.25],
    )
    bridge_base_url: str | None = Field(
        default=None,
        description="Legacy alias of base_url_internal.",
        examples=["https://tehran.example.com"],
    )
    bridge_is_enabled: bool = Field(
        ...,
        description="Legacy status alias. true when status is active.",
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


class CustomerDatabaseConnectionBase(CustomerDatabaseConnectionNormalizer):
    connection_string: str = Field(
        ...,
        description="Full SQLAlchemy SQL Server connection string. This value is stored encrypted and is never returned by the API.",
        examples=[
            "mssql+pyodbc://portal_user:secret@10.10.10.20:1433/CustomerPortalDb?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
        ],
    )
    secret_version: str | None = Field(
        default=None,
        description="Optional secret version or rotation label for the encrypted connection secret.",
        examples=["v3"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether this encrypted customer database connection may be used.",
        examples=[True],
    )
    credential_rotated_at: datetime | None = Field(
        default=None,
        description="Last successful encrypted connection rotation timestamp.",
    )
    rotation_due_at: datetime | None = Field(
        default=None,
        description="Planned next encrypted connection rotation timestamp.",
    )


class CustomerDatabaseConnectionCreate(CustomerDatabaseConnectionBase):
    pass


class CustomerDatabaseConnectionUpdate(CustomerDatabaseConnectionNormalizer):
    connection_string: str | None = Field(
        default=None,
        description="Full SQLAlchemy SQL Server connection string. This value is stored encrypted and is never returned by the API.",
        examples=[
            "mssql+pyodbc://portal_user:secret@10.10.10.20:1433/CustomerPortalDb?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
        ],
    )
    secret_version: str | None = Field(
        default=None,
        description="Optional secret version or rotation label for the encrypted connection secret.",
        examples=["v3"],
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether this encrypted customer database connection may be used.",
        examples=[True],
    )
    credential_rotated_at: datetime | None = Field(default=None, description="Last successful encrypted connection rotation timestamp.")
    rotation_due_at: datetime | None = Field(default=None, description="Planned next encrypted connection rotation timestamp.")

    @model_validator(mode="after")
    def validate_has_updates(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one customer database connection field must be provided.")
        return self


class CustomerDatabaseConnectionOut(MongoDTO):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    customer_name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    db_kind: str = Field(..., description="Database engine kind.", examples=["sqlserver"])
    is_active: bool = Field(..., description="Whether this customer database connection may be used.", examples=[True])
    has_connection_secret: bool = Field(..., description="Whether an encrypted connection string is registered for this customer.", examples=[True])
    secret_version: str | None = Field(default=None, description="Optional secret version or rotation label for the encrypted connection secret.", examples=["v3"])
    credential_rotated_at: datetime | None = Field(default=None, description="Last successful encrypted connection rotation timestamp.")
    rotation_due_at: datetime | None = Field(default=None, description="Planned next encrypted connection rotation timestamp.")
    last_connection_tested_at: datetime | None = Field(default=None, description="Last connection test timestamp.")
    last_connection_test_success: bool | None = Field(default=None, description="Whether the last connection test succeeded.", examples=[True])
    last_connection_error: str | None = Field(default=None, description="Sanitized error message from the last connection test.")


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
