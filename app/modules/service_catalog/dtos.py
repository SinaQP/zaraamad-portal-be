from datetime import datetime

from pydantic import Field, model_validator

from app.common.dtos import MongoDTO, WithId


class ServiceProjectBase(MongoDTO):
    code: str = Field(..., description="Service project code.", examples=["digital-transformation"])
    name: str = Field(..., description="Service project display name.", examples=["Digital Transformation"])
    description: str | None = Field(
        default=None,
        description="Service project description.",
        examples=["Project umbrella for digital service offerings."],
    )
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[10])


class ServiceProjectCreate(ServiceProjectBase):
    pass


class ServiceProjectOut(WithId, ServiceProjectBase):
    is_active: bool = Field(..., description="Service project active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ServiceProjectUpdate(MongoDTO):
    code: str | None = Field(default=None, description="Service project code.", examples=["smart-city"])
    name: str | None = Field(default=None, description="Service project display name.", examples=["Smart City"])
    description: str | None = Field(default=None, description="Service project description.", examples=["City ops"])
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[20])
    is_active: bool | None = Field(default=None, description="Service project active status.", examples=[False])


class ServiceProjectInfo(MongoDTO):
    id: int = Field(..., description="Service project id.", examples=[1])
    code: str = Field(..., description="Service project code.", examples=["digital-transformation"])
    name: str = Field(..., description="Service project name.", examples=["Digital Transformation"])
    is_active: bool = Field(..., description="Service project active status.", examples=[True])


class ServiceGroupBase(MongoDTO):
    project_id: int = Field(..., description="Service project id.", examples=[1])
    code: str = Field(..., description="Service group code.", examples=["security"])
    name: str = Field(..., description="Service group display name.", examples=["Security"])
    description: str | None = Field(
        default=None,
        description="Service group description.",
        examples=["Security-related services."],
    )
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[10])


class ServiceGroupCreate(ServiceGroupBase):
    pass


class ServiceGroupOut(WithId, ServiceGroupBase):
    project: ServiceProjectInfo = Field(..., description="Service project information.")
    is_active: bool = Field(..., description="Service group active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ServiceGroupUpdate(MongoDTO):
    project_id: int | None = Field(default=None, description="Service project id.", examples=[1])
    code: str | None = Field(default=None, description="Service group code.", examples=["taxes"])
    name: str | None = Field(default=None, description="Service group display name.", examples=["Taxes"])
    description: str | None = Field(default=None, description="Service group description.", examples=["Tax services"])
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[20])
    is_active: bool | None = Field(default=None, description="Service group active status.", examples=[False])


class ServiceGroupInfo(MongoDTO):
    id: int = Field(..., description="Service group id.", examples=[1])
    project_id: int = Field(..., description="Service project id.", examples=[1])
    code: str = Field(..., description="Service group code.", examples=["security"])
    name: str = Field(..., description="Service group name.", examples=["Security"])
    is_active: bool = Field(..., description="Service group active status.", examples=[True])


class ServiceBase(MongoDTO):
    group_id: int = Field(..., description="Service group id.", examples=[1])
    code: str = Field(..., description="Service code.", examples=["camera-monitoring"])
    name: str = Field(..., description="Service display name.", examples=["Camera Monitoring"])
    description: str | None = Field(
        default=None,
        description="Service description.",
        examples=["Monitoring and surveillance service."],
    )
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[10])


class ServiceCreate(ServiceBase):
    pass


class ServiceOut(WithId, ServiceBase):
    project_id: int = Field(..., description="Service project id.", examples=[1])
    is_active: bool = Field(..., description="Service active status.", examples=[True])
    project: ServiceProjectInfo = Field(..., description="Service project information.")
    group: ServiceGroupInfo = Field(..., description="Service group information.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ServiceUpdate(MongoDTO):
    group_id: int | None = Field(default=None, description="Service group id.", examples=[1])
    code: str | None = Field(default=None, description="Service code.", examples=["it-support"])
    name: str | None = Field(default=None, description="Service display name.", examples=["IT Support"])
    description: str | None = Field(default=None, description="Service description.", examples=["Support service"])
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[30])
    is_active: bool | None = Field(default=None, description="Service active status.", examples=[True])


class MunicipalityServiceConfigBase(MongoDTO):
    service_id: int = Field(..., description="Service id.", examples=[1])
    is_enabled: bool = Field(..., description="Service enabled for municipality.", examples=[True])
    sale_price: int = Field(..., ge=0, description="Sale price in smallest money unit.", examples=[5000000])
    support_price: int | None = Field(
        default=None,
        ge=0,
        description="Support price in smallest money unit.",
        examples=[1500000],
    )
    notes: str | None = Field(default=None, description="Optional notes.", examples=["Includes emergency support."])


class MunicipalityServiceConfigCreate(MunicipalityServiceConfigBase):
    pass


class MunicipalityServiceConfigOut(WithId, MunicipalityServiceConfigBase):
    municipality_id: int = Field(..., description="Municipality id.", examples=[1])
    project_id: int = Field(..., description="Service project id.", examples=[1])
    project_code: str = Field(..., description="Service project code.", examples=["digital-transformation"])
    project_name: str = Field(..., description="Service project name.", examples=["Digital Transformation"])
    group_id: int = Field(..., description="Service group id.", examples=[1])
    group_code: str = Field(..., description="Service group code.", examples=["security"])
    group_name: str = Field(..., description="Service group name.", examples=["Security"])
    service_code: str = Field(..., description="Service code.", examples=["camera-monitoring"])
    service_name: str = Field(..., description="Service name.", examples=["Camera Monitoring"])
    service_is_active: bool = Field(..., description="Service active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class MunicipalityServiceConfigUpdate(MongoDTO):
    is_enabled: bool | None = Field(default=None, description="Service enabled for municipality.", examples=[False])
    sale_price: int | None = Field(default=None, ge=0, description="Sale price in smallest money unit.", examples=[7000000])
    support_price: int | None = Field(default=None, ge=0, description="Support price in smallest money unit.", examples=[2000000])
    notes: str | None = Field(default=None, description="Optional notes.", examples=["Updated by admin."])


class MunicipalityServiceConfigBulkUpsertBase(MongoDTO):
    items: list[MunicipalityServiceConfigCreate] = Field(
        ...,
        description="Bulk upsert items for municipality-service configurations.",
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
    grade: int = Field(..., description="Municipality grade.", examples=[1])


class MunicipalityPricingSummaryItem(MongoDTO):
    service_id: int = Field(..., description="Service id.", examples=[1])
    service_code: str = Field(..., description="Service code.", examples=["camera-monitoring"])
    service_name: str = Field(..., description="Service name.", examples=["Camera Monitoring"])
    is_enabled: bool = Field(..., description="Enabled state for municipality.", examples=[True])
    sale_price: int = Field(..., description="Configured sale price.", examples=[5000000])
    support_price: int | None = Field(default=None, description="Configured support price.", examples=[1500000])
    line_sale_total: int = Field(..., description="Line sale total.", examples=[5000000])
    line_support_total: int = Field(..., description="Line support total.", examples=[1500000])
    line_grand_total: int = Field(..., description="Line grand total.", examples=[6500000])


class MunicipalityPricingSummaryGroupTotals(MongoDTO):
    sale_total: int = Field(..., description="Group sale total.", examples=[5000000])
    support_total: int = Field(..., description="Group support total.", examples=[1500000])
    grand_total: int = Field(..., description="Group grand total.", examples=[6500000])


class MunicipalityPricingSummaryGroup(MongoDTO):
    project_id: int = Field(..., description="Service project id.", examples=[1])
    project_code: str = Field(..., description="Service project code.", examples=["digital-transformation"])
    project_name: str = Field(..., description="Service project name.", examples=["Digital Transformation"])
    group_id: int = Field(..., description="Service group id.", examples=[1])
    group_code: str = Field(..., description="Service group code.", examples=["security"])
    group_name: str = Field(..., description="Service group name.", examples=["Security"])
    items: list[MunicipalityPricingSummaryItem] = Field(..., description="Group items.")
    totals: MunicipalityPricingSummaryGroupTotals = Field(..., description="Group totals.")


class MunicipalityPricingSummaryTotals(MongoDTO):
    sale_total: int = Field(..., description="Overall sale total.", examples=[12000000])
    support_total: int = Field(..., description="Overall support total.", examples=[3000000])
    grand_total: int = Field(..., description="Overall grand total.", examples=[15000000])


class MunicipalityPricingSummaryResult(MongoDTO):
    municipality: MunicipalityPricingSummaryMunicipality = Field(..., description="Municipality information.")
    groups: list[MunicipalityPricingSummaryGroup] = Field(..., description="Services grouped by service group.")
    totals: MunicipalityPricingSummaryTotals = Field(..., description="Overall pricing totals.")
