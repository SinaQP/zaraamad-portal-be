from datetime import datetime

from pydantic import Field, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.messages import ITEMS_MUST_NOT_BE_EMPTY
from app.common.pagination import PaginatedResponse


class ServiceProjectBase(MongoDTO):
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


class ServiceProjectListOut(PaginatedResponse[ServiceProjectOut]):
    pass


class ServiceProjectUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Service project display name.", examples=["Smart City"])
    description: str | None = Field(default=None, description="Service project description.", examples=["City ops"])
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[20])
    is_active: bool | None = Field(default=None, description="Service project active status.", examples=[False])


class ServiceProjectInfo(MongoDTO):
    id: int = Field(..., description="Service project id.", examples=[1])
    name: str = Field(..., description="Service project name.", examples=["Digital Transformation"])
    is_active: bool = Field(..., description="Service project active status.", examples=[True])


class ServiceGroupBase(MongoDTO):
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
    is_active: bool = Field(..., description="Service group active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ServiceGroupListOut(PaginatedResponse[ServiceGroupOut]):
    pass


class ServiceGroupUpdate(MongoDTO):
    name: str | None = Field(default=None, description="Service group display name.", examples=["Taxes"])
    description: str | None = Field(default=None, description="Service group description.", examples=["Tax services"])
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[20])
    is_active: bool | None = Field(default=None, description="Service group active status.", examples=[False])


class ServiceGroupInfo(MongoDTO):
    id: int = Field(..., description="Service group id.", examples=[1])
    name: str = Field(..., description="Service group name.", examples=["Security"])
    is_active: bool = Field(..., description="Service group active status.", examples=[True])


class ServiceBase(MongoDTO):
    project_id: int = Field(..., description="Service project id.", examples=[1])
    group_id: int = Field(..., description="Service group id.", examples=[1])
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
    is_active: bool = Field(..., description="Service active status.", examples=[True])
    project: ServiceProjectInfo = Field(..., description="Service project information.")
    group: ServiceGroupInfo = Field(..., description="Service group information.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ServiceListOut(PaginatedResponse[ServiceOut]):
    pass


class ServiceUpdate(MongoDTO):
    project_id: int | None = Field(default=None, description="Service project id.", examples=[1])
    group_id: int | None = Field(default=None, description="Service group id.", examples=[1])
    name: str | None = Field(default=None, description="Service display name.", examples=["IT Support"])
    description: str | None = Field(default=None, description="Service description.", examples=["Support service"])
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[30])
    is_active: bool | None = Field(default=None, description="Service active status.", examples=[True])


class ServiceProjectHierarchyServiceOut(WithId, MongoDTO):
    name: str = Field(..., description="Service display name.", examples=["Camera Monitoring"])
    description: str | None = Field(default=None, description="Service description.")
    sort_order: int | None = Field(default=None, description="Sort order for listing.", examples=[10])
    is_active: bool = Field(..., description="Service active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ServiceProjectHierarchyGroupOut(ServiceGroupOut):
    services: list[ServiceProjectHierarchyServiceOut] = Field(..., description="Services inside this group.")


class ServiceProjectHierarchyProjectOut(ServiceProjectOut):
    groups: list[ServiceProjectHierarchyGroupOut] = Field(..., description="Groups and services for this project.")


class CustomerServiceConfigBase(MongoDTO):
    service_id: int = Field(..., description="Service id.", examples=[1])
    is_enabled: bool = Field(..., description="Service enabled for customer.", examples=[True])
    sale_price: int | None = Field(
        default=None,
        ge=0,
        description="Sale price in smallest money unit.",
        examples=[5000000],
    )
    support_price: int = Field(
        ...,
        ge=0,
        description="Support price in smallest money unit.",
        examples=[1500000],
    )
    notes: str | None = Field(default=None, description="Optional notes.", examples=["Includes emergency support."])


class CustomerServiceConfigCreate(CustomerServiceConfigBase):
    pass


class CustomerServiceConfigOut(WithId, CustomerServiceConfigBase):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    project_id: int = Field(..., description="Service project id.", examples=[1])
    project_name: str = Field(..., description="Service project name.", examples=["Digital Transformation"])
    group_id: int = Field(..., description="Service group id.", examples=[1])
    group_name: str = Field(..., description="Service group name.", examples=["Security"])
    service_name: str = Field(..., description="Service name.", examples=["Camera Monitoring"])
    service_is_active: bool = Field(..., description="Service active status.", examples=[True])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class CustomerServiceConfigListOut(PaginatedResponse[CustomerServiceConfigOut]):
    pass


class CustomerServiceConfigUpdate(MongoDTO):
    is_enabled: bool | None = Field(default=None, description="Service enabled for customer.", examples=[False])
    sale_price: int | None = Field(default=None, ge=0, description="Sale price in smallest money unit.", examples=[7000000])
    support_price: int | None = Field(default=None, ge=0, description="Support price in smallest money unit.", examples=[2000000])
    notes: str | None = Field(default=None, description="Optional notes.", examples=["Updated by admin."])


class CustomerServiceConfigBulkUpsertBase(MongoDTO):
    items: list[CustomerServiceConfigCreate] = Field(
        ...,
        description="Bulk upsert items for customer-service configurations.",
    )

    @model_validator(mode="after")
    def validate_non_empty_items(self) -> "CustomerServiceConfigBulkUpsertBase":
        if len(self.items) == 0:
            raise ValueError(ITEMS_MUST_NOT_BE_EMPTY)
        return self


class CustomerServiceConfigBulkUpsertCreate(CustomerServiceConfigBulkUpsertBase):
    pass


class CustomerPricingSummaryCustomer(MongoDTO):
    id: int = Field(..., description="Customer id.", examples=[1])
    name: str = Field(..., description="Customer name.", examples=["Tehran Customer"])
    grade: int = Field(..., description="Customer grade.", examples=[1])


class CustomerPricingSummaryItem(MongoDTO):
    service_id: int = Field(..., description="Service id.", examples=[1])
    service_name: str = Field(..., description="Service name.", examples=["Camera Monitoring"])
    is_enabled: bool = Field(..., description="Enabled state for customer.", examples=[True])
    sale_price: int | None = Field(default=None, description="Configured sale price.", examples=[5000000])
    support_price: int = Field(..., description="Configured support price.", examples=[1500000])
    line_sale_total: int = Field(..., description="Line sale total.", examples=[5000000])
    line_support_total: int = Field(..., description="Line support total.", examples=[1500000])
    line_grand_total: int = Field(..., description="Line grand total.", examples=[6500000])


class CustomerPricingSummaryGroupTotals(MongoDTO):
    sale_total: int = Field(..., description="Group sale total.", examples=[5000000])
    support_total: int = Field(..., description="Group support total.", examples=[1500000])
    grand_total: int = Field(..., description="Group grand total.", examples=[6500000])


class CustomerPricingSummaryGroup(MongoDTO):
    project_id: int = Field(..., description="Service project id.", examples=[1])
    project_name: str = Field(..., description="Service project name.", examples=["Digital Transformation"])
    group_id: int = Field(..., description="Service group id.", examples=[1])
    group_name: str = Field(..., description="Service group name.", examples=["Security"])
    items: list[CustomerPricingSummaryItem] = Field(..., description="Group items.")
    totals: CustomerPricingSummaryGroupTotals = Field(..., description="Group totals.")


class CustomerPricingSummaryTotals(MongoDTO):
    sale_total: int = Field(..., description="Overall sale total.", examples=[12000000])
    support_total: int = Field(..., description="Overall support total.", examples=[3000000])
    grand_total: int = Field(..., description="Overall grand total.", examples=[15000000])


class CustomerPricingSummaryResult(MongoDTO):
    customer: CustomerPricingSummaryCustomer = Field(..., description="Customer information.")
    groups: list[CustomerPricingSummaryGroup] = Field(..., description="Services grouped by service group.")
    totals: CustomerPricingSummaryTotals = Field(..., description="Overall pricing totals.")
