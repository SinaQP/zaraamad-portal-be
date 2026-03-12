from typing import Self

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.pagination import PaginatedResponse


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
    grade: int = Field(..., description="Customer grade.", examples=[1])


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(WithId, CustomerBase):
    is_active: bool = Field(..., description="Customer active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class CustomerListOut(PaginatedResponse[CustomerOut]):
    pass


class CustomerUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Customer name.", examples=["Qom Customer"])
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
