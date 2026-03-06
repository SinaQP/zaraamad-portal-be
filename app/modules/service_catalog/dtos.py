from datetime import datetime

from pydantic import Field, model_validator

from app.common.dtos import MongoDTO, WithId


class ServiceBase(MongoDTO):
    name: str = Field(..., description="Service display name.", examples=["Security Services"])
    description: str | None = Field(
        default=None,
        description="Service description.",
        examples=["On-site and monitoring security services."],
    )
    sort_order: int | None = Field(
        default=None,
        description="Sort order for listing.",
        examples=[10],
    )


class ServiceCreate(ServiceBase):
    pass


class ServiceOut(WithId, ServiceBase):
    is_active: bool = Field(..., description="Service active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ServiceUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Service display name.", examples=["Support Services"])
    description: str | None = Field(
        default=None,
        description="Service description.",
        examples=["Ticketing and call-center support."],
    )
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[20])
    is_active: bool | None = Field(default=None, description="Service active status.", examples=[True])


class MunicipalityServiceConfigBase(MongoDTO):
    service_id: int = Field(..., description="Service id.", examples=[1])
    is_enabled: bool = Field(..., description="Service enabled for municipality.", examples=[True])
    unit_price: int = Field(..., ge=0, description="Service unit price in smallest money unit.", examples=[5000000])
    notes: str | None = Field(
        default=None,
        description="Optional notes for municipality-specific configuration.",
        examples=["Includes night shift coverage."],
    )


class MunicipalityServiceConfigCreate(MunicipalityServiceConfigBase):
    pass


class MunicipalityServiceConfigOut(WithId, MunicipalityServiceConfigBase):
    municipality_id: int = Field(..., description="Municipality id.", examples=[1])
    service_name: str = Field(..., description="Service name.", examples=["Security Services"])
    service_is_active: bool = Field(..., description="Service active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class MunicipalityServiceConfigUpdate(MongoDTO):
    is_enabled: bool | None = Field(default=None, description="Service enabled for municipality.", examples=[False])
    unit_price: int | None = Field(
        default=None,
        ge=0,
        description="Service unit price in smallest money unit.",
        examples=[7000000],
    )
    notes: str | None = Field(default=None, description="Optional notes.", examples=["Updated by admin."])


class MunicipalityServiceConfigBulkUpsertBase(MongoDTO):
    items: list[MunicipalityServiceConfigCreate] = Field(
        ...,
        description="Bulk upsert items for municipality service configuration.",
    )

    @model_validator(mode="after")
    def validate_non_empty_items(self) -> "MunicipalityServiceConfigBulkUpsertBase":
        if len(self.items) == 0:
            raise ValueError("items must not be empty.")
        return self


class MunicipalityServiceConfigBulkUpsertCreate(MunicipalityServiceConfigBulkUpsertBase):
    pass


class MunicipalityPricingSummaryMunicipality(MongoDTO):
    id: int = Field(..., description="Municipality id.", examples=[1])
    name: str = Field(..., description="Municipality name.", examples=["Tehran Municipality"])
    code: str = Field(..., description="Municipality code.", examples=["THR-001"])


class MunicipalityPricingSummaryItem(MongoDTO):
    service_id: int = Field(..., description="Service id.", examples=[1])
    service_name: str = Field(..., description="Service name.", examples=["Security Services"])
    is_enabled: bool = Field(..., description="Enabled state for municipality.", examples=[True])
    unit_price: int = Field(..., description="Configured unit price.", examples=[5000000])
    line_total: int = Field(..., description="Line total for summary calculations.", examples=[5000000])


class MunicipalityPricingSummaryTotals(MongoDTO):
    enabled_total: int = Field(..., description="Total price for enabled items.", examples=[20000000])
    configured_total: int = Field(..., description="Total price for all configured items.", examples=[25000000])


class MunicipalityPricingSummaryResult(MongoDTO):
    municipality: MunicipalityPricingSummaryMunicipality = Field(
        ...,
        description="Municipality information.",
    )
    items: list[MunicipalityPricingSummaryItem] = Field(
        ...,
        description="Municipality service configuration items.",
    )
    totals: MunicipalityPricingSummaryTotals = Field(
        ...,
        description="Pricing totals for enabled and all configured items.",
    )
