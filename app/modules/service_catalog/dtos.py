from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.common.dtos import MongoDTO, WithId
from app.common.messages import ITEMS_MUST_NOT_BE_EMPTY
from app.common.pagination import PaginatedResponse
from app.common.validators.jalali_datetime import validate_jalali_datetime_string
from app.modules.customers.dtos import CustomerOut


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


class CustomerServicePurchaseItemBase(MongoDTO):
    customer_service_config_id: int = Field(
        ...,
        description="Customer service config id.",
        examples=[1],
    )


class CustomerServicePurchaseItemCreate(CustomerServicePurchaseItemBase):
    pass


class CustomerServicePurchaseItemOut(WithId, CustomerServicePurchaseItemBase):
    service_id: int = Field(..., description="Service id.", examples=[1])
    project_id: int = Field(..., description="Service project id.", examples=[1])
    project_name: str = Field(..., description="Service project name.", examples=["Digital Transformation"])
    group_id: int = Field(..., description="Service group id.", examples=[1])
    group_name: str = Field(..., description="Service group name.", examples=["Security"])
    service_name: str = Field(..., description="Service name.", examples=["Camera Monitoring"])
    sale_price: int | None = Field(default=None, description="Selected sale price.", examples=[5000000])
    support_price: int = Field(..., description="Selected support price.", examples=[1500000])
    line_sale_total: int = Field(..., description="Line sale total.", examples=[5000000])
    line_support_total: int = Field(..., description="Line support total.", examples=[1500000])
    line_grand_total: int = Field(..., description="Line grand total.", examples=[6500000])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class CustomerServicePurchaseBase(MongoDTO):
    notes: str | None = Field(
        default=None,
        description="Optional purchase notes.",
        examples=["User selected the essential services only."],
    )


class CustomerServicePurchaseCreate(CustomerServicePurchaseBase):
    items: list[CustomerServicePurchaseItemCreate] = Field(
        ...,
        description="Selected customer service configs for this purchase.",
    )

    @model_validator(mode="after")
    def validate_non_empty_items(self) -> "CustomerServicePurchaseCreate":
        if len(self.items) == 0:
            raise ValueError(ITEMS_MUST_NOT_BE_EMPTY)
        return self


class CustomerServicePurchaseOut(WithId, CustomerServicePurchaseBase):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    created_by_user_id: int = Field(..., description="Creator user id.", examples=[7])
    selected_count: int = Field(..., description="Count of selected services.", examples=[5])
    sale_total: int = Field(..., description="Total sale amount.", examples=[12000000])
    support_total: int = Field(..., description="Total support amount.", examples=[3000000])
    grand_total: int = Field(..., description="Total payable amount.", examples=[15000000])
    is_active: bool = Field(..., description="Purchase active status.", examples=[True])
    items: list[CustomerServicePurchaseItemOut] = Field(
        ...,
        description="Selected service items captured for this purchase.",
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class CustomerServicePurchaseListOut(PaginatedResponse[CustomerServicePurchaseOut]):
    pass


class CustomerServicePurchaseUpdate(CustomerServicePurchaseBase):
    notes: str | None = Field(
        default=None,
        description="Optional purchase notes.",
        examples=["Updated after final review."],
    )
    items: list[CustomerServicePurchaseItemCreate] | None = Field(
        default=None,
        description="Replacement list of selected customer service configs.",
    )

    @model_validator(mode="after")
    def validate_items_when_present(self) -> "CustomerServicePurchaseUpdate":
        if self.items is not None and len(self.items) == 0:
            raise ValueError(ITEMS_MUST_NOT_BE_EMPTY)
        return self


class CustomerServiceSelectionSnapshotBase(MongoDTO):
    user_id: int = Field(..., description="User id that registered this snapshot.", examples=[7])
    selected_at: str = Field(
        ...,
        description="Selection datetime as a Jalali string in YYYY-MM-DD HH:MM:SS format.",
        examples=["1405-01-05 10:30:00"],
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Complete frontend payload captured as a JSON object.",
        examples=[
            {
                "project_id": 3,
                "selected_config_ids": [11, 12],
                "totals": {"sale_total": 1200, "support_total": 50, "grand_total": 1250},
            }
        ],
    )

    @field_validator("selected_at")
    @classmethod
    def validate_selected_at(cls, value: str) -> str:
        return validate_jalali_datetime_string(value)


class CustomerServiceSelectionSnapshotCreate(CustomerServiceSelectionSnapshotBase):
    pass


class CustomerServiceSelectionSnapshotOut(WithId, CustomerServiceSelectionSnapshotBase):
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class CustomerServiceSelectionSnapshotListOut(PaginatedResponse[CustomerServiceSelectionSnapshotOut]):
    pass


class CustomerServiceTreeTotalsOut(MongoDTO):
    configured_service_count: int = Field(..., description="Count of configured services.", examples=[3])
    enabled_service_count: int = Field(..., description="Count of enabled services.", examples=[2])
    sale_total: int = Field(..., description="Aggregated sale total.", examples=[12000000])
    support_total: int = Field(..., description="Aggregated support total.", examples=[3000000])
    grand_total: int = Field(..., description="Aggregated grand total.", examples=[15000000])


class CustomerServiceTreeServiceOut(MongoDTO):
    config_id: int = Field(..., description="Customer service config id.", examples=[1])
    customer_id: int = Field(..., description="Customer id.", examples=[1])
    service_id: int = Field(..., description="Service id.", examples=[10])
    service_name: str = Field(..., description="Service name.", examples=["Camera Monitoring"])
    service_description: str | None = Field(
        default=None,
        description="Service description.",
        examples=["Monitoring and surveillance service."],
    )
    service_sort_order: int | None = Field(default=None, description="Service sort order.", examples=[10])
    service_is_active: bool = Field(..., description="Service active status.", examples=[True])
    is_enabled: bool = Field(..., description="Whether the service is enabled for the customer.", examples=[True])
    sale_price: int | None = Field(default=None, description="Configured sale price.", examples=[5000000])
    support_price: int = Field(..., description="Configured support price.", examples=[1500000])
    notes: str | None = Field(default=None, description="Optional service notes.", examples=["Includes setup."])
    line_sale_total: int = Field(..., description="Line sale total.", examples=[5000000])
    line_support_total: int = Field(..., description="Line support total.", examples=[1500000])
    line_grand_total: int = Field(..., description="Line grand total.", examples=[6500000])
    config_created_at: datetime = Field(..., description="Customer service config creation timestamp.")
    config_updated_at: datetime = Field(..., description="Customer service config last update timestamp.")
    service_created_at: datetime = Field(..., description="Service catalog creation timestamp.")
    service_updated_at: datetime = Field(..., description="Service catalog last update timestamp.")


class CustomerServiceTreeGroupOut(ServiceGroupOut):
    totals: CustomerServiceTreeTotalsOut = Field(..., description="Aggregated totals for this group.")
    services: list[CustomerServiceTreeServiceOut] = Field(
        ...,
        description="Customer services inside this group.",
    )


class CustomerServiceTreeProjectOut(ServiceProjectOut):
    totals: CustomerServiceTreeTotalsOut = Field(..., description="Aggregated totals for this project.")
    groups: list[CustomerServiceTreeGroupOut] = Field(
        ...,
        description="Nested service groups for this project.",
    )


class CustomerServiceTreeOut(MongoDTO):
    customer: CustomerOut = Field(..., description="Full customer information.")
    projects: list[CustomerServiceTreeProjectOut] = Field(
        ...,
        description="Customer services grouped by project and group.",
    )
    totals: CustomerServiceTreeTotalsOut = Field(..., description="Overall customer service totals.")


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
