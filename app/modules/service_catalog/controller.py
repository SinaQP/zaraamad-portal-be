from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.dtos import CurrentUser
from app.common.enums import SortOrder
from app.common.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.common.security.dependencies import get_current_user, require_admin
from app.modules.service_catalog.dtos import (
    CustomerServiceConfigListOut,
    CustomerServiceConfigBulkUpsertCreate,
    CustomerServiceConfigOut,
    CustomerServiceTreeOut,
    CustomerServiceConfigUpdate,
    CustomerPricingSummaryResult,
    CustomerServicePurchaseCreate,
    CustomerServicePurchaseListOut,
    CustomerServicePurchaseOut,
    CustomerServicePurchaseUpdate,
    ServiceCreate,
    ServiceGroupListOut,
    ServiceGroupCreate,
    ServiceGroupOut,
    ServiceGroupUpdate,
    ServiceListOut,
    ServiceOut,
    ServiceProjectHierarchyProjectOut,
    ServiceProjectCreate,
    ServiceProjectListOut,
    ServiceProjectOut,
    ServiceProjectUpdate,
    ServiceUpdate,
)
from app.modules.service_catalog.mappers import ServiceCatalogMapper, get_service_catalog_mapper
from app.modules.service_catalog.service import (
    CustomerPricingSummaryService,
    CustomerServiceConfigService,
    CustomerServicePurchaseService,
    CustomerServiceTreeService,
    ServiceCatalogService,
    ServiceGroupService,
    ServiceProjectService,
    get_customer_pricing_summary_service,
    get_customer_service_config_service,
    get_customer_service_purchase_service,
    get_customer_service_tree_service,
    get_service_catalog_service,
    get_service_group_service,
    get_service_project_service,
)

SERVICE_PROJECTS_TAG = "service-projects"
SERVICE_GROUPS_TAG = "service-groups"
SERVICES_TAG = "services"
CUSTOMER_SERVICE_CONFIGS_TAG = "customer-service-configs"
CUSTOMER_SERVICE_PURCHASES_TAG = "customer-service-purchases"
CUSTOMER_SERVICE_TREE_TAG = "customer-service-tree"
CUSTOMER_PRICING_TAG = "customer-pricing"

router = APIRouter()


@router.post(
    "/service-projects",
    tags=[SERVICE_PROJECTS_TAG],
    response_model=ServiceProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create service project",
    description="Create a new top-level service project. Only admin users can access this endpoint.",
    responses={
        201: {"description": "Service project created."},
        403: {"description": "Admin access required."},
        409: {"description": "Data integrity error."},
    },
)
def create_service_project(
    payload: ServiceProjectCreate,
    _: object = Depends(require_admin),
    service: ServiceProjectService = Depends(get_service_project_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceProjectOut:
    project = service.create(dto=payload)
    return mapper.to_service_project_out(project=project)


@router.get(
    "/service-projects",
    tags=[SERVICE_PROJECTS_TAG],
    response_model=ServiceProjectListOut,
    summary="List service projects",
    description="Return service projects with optional active-state filtering.",
    responses={
        200: {"description": "Service project list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_service_projects(
    response: Response,
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    search: str | None = Query(default=None, description="Search by project name or description."),
    sort_by: Literal["id", "name", "sort_order", "is_active", "created_at", "updated_at"] = Query(
        default="sort_order",
        description="Sort field.",
    ),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    _: object = Depends(require_admin),
    service: ServiceProjectService = Depends(get_service_project_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceProjectListOut:
    projects, meta = service.list(
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )
    set_pagination_headers(response=response, meta=meta)
    return ServiceProjectListOut(
        items=[mapper.to_service_project_out(project=item) for item in projects],
        total_page=meta.total_pages,
    )


@router.get(
    "/service-projects/all",
    tags=[SERVICE_PROJECTS_TAG],
    response_model=list[ServiceProjectOut],
    summary="Get all service projects",
    description="Return all service projects without pagination for select inputs.",
    responses={
        200: {"description": "All service projects returned."},
        403: {"description": "Admin access required."},
    },
)
def get_all_service_projects(
    _: object = Depends(require_admin),
    service: ServiceProjectService = Depends(get_service_project_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[ServiceProjectOut]:
    projects = service.list_all()
    return [mapper.to_service_project_out(project=item) for item in projects]


@router.get(
    "/service-projects/hierarchy",
    tags=[SERVICE_PROJECTS_TAG],
    response_model=list[ServiceProjectHierarchyProjectOut],
    summary="List service hierarchy by project",
    description="Return projects and nest their groups and services under each project.",
    responses={
        200: {"description": "Service hierarchy returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Service project not found."},
    },
)
def list_service_project_hierarchy(
    project_id: int | None = Query(default=None, description="Filter to a single service project id."),
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[ServiceProjectHierarchyProjectOut]:
    items = service.list_grouped_by_project(project_id=project_id)
    return [
        mapper.to_service_project_hierarchy_project_out(
            project=item.project,
            groups=[(group_item.group, group_item.services) for group_item in item.groups],
        )
        for item in items
    ]


@router.get(
    "/service-projects/{project_id}",
    tags=[SERVICE_PROJECTS_TAG],
    response_model=ServiceProjectOut,
    summary="Get service project",
    description="Return a service project by id.",
    responses={
        200: {"description": "Service project returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Service project not found."},
    },
)
def get_service_project(
    project_id: int,
    _: object = Depends(require_admin),
    service: ServiceProjectService = Depends(get_service_project_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceProjectOut:
    project = service.get_active_or_404(project_id=project_id)
    return mapper.to_service_project_out(project=project)


@router.patch(
    "/service-projects/{project_id}",
    tags=[SERVICE_PROJECTS_TAG],
    response_model=ServiceProjectOut,
    summary="Update service project",
    description="Partially update a service project by id.",
    responses={
        200: {"description": "Service project updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Service project not found."},
        409: {"description": "Data integrity error."},
    },
)
def update_service_project(
    project_id: int,
    payload: ServiceProjectUpdate,
    _: object = Depends(require_admin),
    service: ServiceProjectService = Depends(get_service_project_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceProjectOut:
    project = service.update(project_id=project_id, dto=payload)
    return mapper.to_service_project_out(project=project)


@router.delete(
    "/service-projects/{project_id}",
    tags=[SERVICE_PROJECTS_TAG],
    response_model=ServiceProjectOut,
    summary="Deactivate service project",
    description="Soft delete service project by setting is_active=false.",
    responses={
        200: {"description": "Service project deactivated."},
        403: {"description": "Admin access required."},
        404: {"description": "Service project not found."},
    },
)
def deactivate_service_project(
    project_id: int,
    _: object = Depends(require_admin),
    service: ServiceProjectService = Depends(get_service_project_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceProjectOut:
    project = service.deactivate(project_id=project_id)
    return mapper.to_service_project_out(project=project)


@router.post(
    "/service-groups",
    tags=[SERVICE_GROUPS_TAG],
    response_model=ServiceGroupOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create service group",
    description="Create a new reusable service group. Only admin users can access this endpoint.",
    responses={
        201: {"description": "Service group created."},
        403: {"description": "Admin access required."},
        409: {"description": "Data integrity error."},
    },
)
def create_service_group(
    payload: ServiceGroupCreate,
    _: object = Depends(require_admin),
    service: ServiceGroupService = Depends(get_service_group_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceGroupOut:
    group = service.create(dto=payload)
    return mapper.to_service_group_out(group=group)


@router.get(
    "/service-groups",
    tags=[SERVICE_GROUPS_TAG],
    response_model=ServiceGroupListOut,
    summary="List service groups",
    description="Return service groups with optional active-state filtering.",
    responses={
        200: {"description": "Service group list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_service_groups(
    response: Response,
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    search: str | None = Query(default=None, description="Search by group name or description."),
    sort_by: Literal[
        "id",
        "name",
        "sort_order",
        "is_active",
        "created_at",
        "updated_at",
    ] = Query(
        default="sort_order",
        description="Sort field.",
    ),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    _: object = Depends(require_admin),
    service: ServiceGroupService = Depends(get_service_group_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceGroupListOut:
    groups, meta = service.list(
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )
    set_pagination_headers(response=response, meta=meta)
    return ServiceGroupListOut(
        items=[mapper.to_service_group_out(group=item) for item in groups],
        total_page=meta.total_pages,
    )


@router.get(
    "/service-groups/all",
    tags=[SERVICE_GROUPS_TAG],
    response_model=list[ServiceGroupOut],
    summary="Get all service groups",
    description="Return all service groups without pagination for select inputs.",
    responses={
        200: {"description": "All service groups returned."},
        403: {"description": "Admin access required."},
    },
)
def get_all_service_groups(
    _: object = Depends(require_admin),
    service: ServiceGroupService = Depends(get_service_group_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[ServiceGroupOut]:
    groups = service.list_all()
    return [mapper.to_service_group_out(group=item) for item in groups]


@router.get(
    "/service-groups/{group_id}",
    tags=[SERVICE_GROUPS_TAG],
    response_model=ServiceGroupOut,
    summary="Get service group",
    description="Return a service group by id.",
    responses={
        200: {"description": "Service group returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Service group not found."},
    },
)
def get_service_group(
    group_id: int,
    _: object = Depends(require_admin),
    service: ServiceGroupService = Depends(get_service_group_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceGroupOut:
    group = service.get_active_or_404(group_id=group_id)
    return mapper.to_service_group_out(group=group)


@router.patch(
    "/service-groups/{group_id}",
    tags=[SERVICE_GROUPS_TAG],
    response_model=ServiceGroupOut,
    summary="Update service group",
    description="Partially update a service group by id.",
    responses={
        200: {"description": "Service group updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Service group not found."},
        409: {"description": "Data integrity error."},
    },
)
def update_service_group(
    group_id: int,
    payload: ServiceGroupUpdate,
    _: object = Depends(require_admin),
    service: ServiceGroupService = Depends(get_service_group_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceGroupOut:
    group = service.update(group_id=group_id, dto=payload)
    return mapper.to_service_group_out(group=group)


@router.delete(
    "/service-groups/{group_id}",
    tags=[SERVICE_GROUPS_TAG],
    response_model=ServiceGroupOut,
    summary="Deactivate service group",
    description="Soft delete service group by setting is_active=false.",
    responses={
        200: {"description": "Service group deactivated."},
        403: {"description": "Admin access required."},
        404: {"description": "Service group not found."},
    },
)
def deactivate_service_group(
    group_id: int,
    _: object = Depends(require_admin),
    service: ServiceGroupService = Depends(get_service_group_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceGroupOut:
    group = service.deactivate(group_id=group_id)
    return mapper.to_service_group_out(group=group)


@router.post(
    "/services",
    tags=[SERVICES_TAG],
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create service catalog item",
    description="Create a new service catalog item with both project and group references. Only admin users can access this endpoint.",
    responses={
        201: {"description": "Service created."},
        403: {"description": "Admin access required."},
        409: {"description": "Data integrity error."},
    },
)
def create_service(
    payload: ServiceCreate,
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceOut:
    created_service, group, project = service.create(dto=payload)
    return mapper.to_service_out(service=created_service, group=group, project=project)


@router.get(
    "/services",
    tags=[SERVICES_TAG],
    response_model=ServiceListOut,
    summary="List service catalog items",
    description="Return global services with optional project, group, and active-state filtering.",
    responses={
        200: {"description": "Service list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_services(
    response: Response,
    project_id: int | None = Query(default=None, description="Filter by service project id."),
    group_id: int | None = Query(default=None, description="Filter by service group id."),
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    search: str | None = Query(default=None, description="Search by project, group, or service name and description."),
    sort_by: Literal[
        "id",
        "project_id",
        "group_id",
        "project_sort_order",
        "group_sort_order",
        "name",
        "sort_order",
        "is_active",
        "created_at",
        "updated_at",
    ] = Query(default="project_sort_order", description="Sort field."),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceListOut:
    services, meta = service.list(
        project_id=project_id,
        group_id=group_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )
    set_pagination_headers(response=response, meta=meta)
    return ServiceListOut(
        items=[mapper.to_service_out(service=item, group=group, project=project) for item, group, project in services],
        total_page=meta.total_pages,
    )


@router.get(
    "/services/{service_id}",
    tags=[SERVICES_TAG],
    response_model=ServiceOut,
    summary="Get service catalog item",
    description="Return a service catalog item by id.",
    responses={
        200: {"description": "Service returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Service not found."},
    },
)
def get_service(
    service_id: int,
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceOut:
    item, group, project = service.get_active_or_404(service_id=service_id)
    return mapper.to_service_out(service=item, group=group, project=project)


@router.patch(
    "/services/{service_id}",
    tags=[SERVICES_TAG],
    response_model=ServiceOut,
    summary="Update service catalog item",
    description="Partially update a service catalog item by id.",
    responses={
        200: {"description": "Service updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Service not found."},
        409: {"description": "Data integrity error."},
    },
)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceOut:
    updated_service, group, project = service.update(service_id=service_id, dto=payload)
    return mapper.to_service_out(service=updated_service, group=group, project=project)


@router.delete(
    "/services/{service_id}",
    tags=[SERVICES_TAG],
    response_model=ServiceOut,
    summary="Deactivate service catalog item",
    description="Soft delete service by setting is_active=false.",
    responses={
        200: {"description": "Service deactivated."},
        403: {"description": "Admin access required."},
        404: {"description": "Service not found."},
    },
)
def deactivate_service(
    service_id: int,
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> ServiceOut:
    deactivated_service, group, project = service.deactivate(service_id=service_id)
    return mapper.to_service_out(service=deactivated_service, group=group, project=project)


@router.get(
    "/customers/{customer_id}/services/tree",
    tags=[CUSTOMER_SERVICE_TREE_TAG],
    response_model=CustomerServiceTreeOut,
    summary="Get customer service tree",
    description=(
        "Return full customer data together with all configured services nested as "
        "project -> group -> service, including prices, notes, and aggregated totals. "
        "Accessible by admin users and the owning customer user."
    ),
    responses={
        200: {"description": "Customer service tree returned."},
        401: {"description": "Authentication required."},
        403: {"description": "Customer access denied."},
        404: {"description": "Customer not found."},
    },
)
def get_customer_service_tree(
    customer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: CustomerServiceTreeService = Depends(get_customer_service_tree_service),
) -> CustomerServiceTreeOut:
    return service.get_tree(
        customer_id=customer_id,
        current_user=current_user,
    )


@router.get(
    "/customers/{customer_id}/services",
    tags=[CUSTOMER_SERVICE_CONFIGS_TAG],
    response_model=CustomerServiceConfigListOut,
    summary="List customer service configs",
    description="Return all configured services for a customer with project, group, price, and enabled status. Accessible by admin users and the owning customer user.",
    responses={
        200: {"description": "Customer service configs returned."},
        401: {"description": "Authentication required."},
        403: {"description": "Customer access denied."},
        404: {"description": "Customer not found."},
    },
)
def list_customer_services(
    response: Response,
    customer_id: int,
    project_id: int | None = Query(default=None, description="Filter by service project id."),
    is_enabled: bool | None = Query(default=None, description="Filter by enabled state."),
    search: str | None = Query(default=None, description="Search by project, group, or service name, or notes."),
    sort_by: Literal[
        "id",
        "project_id",
        "project_name",
        "project_sort_order",
        "service_id",
        "service_name",
        "group_name",
        "group_sort_order",
        "service_sort_order",
        "is_enabled",
        "sale_price",
        "support_price",
        "created_at",
        "updated_at",
    ] = Query(default="project_sort_order", description="Sort field."),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: CurrentUser = Depends(get_current_user),
    service: CustomerServiceConfigService = Depends(get_customer_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServiceConfigListOut:
    rows, meta = service.list_by_customer(
        customer_id=customer_id,
        project_id=project_id,
        is_enabled=is_enabled,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
        current_user=current_user,
    )
    set_pagination_headers(response=response, meta=meta)
    return CustomerServiceConfigListOut(
        items=[
            mapper.to_customer_config_out(config=config, service=service_item, group=group, project=project)
            for config, service_item, group, project in rows
        ],
        total_page=meta.total_pages,
    )


@router.put(
    "/customers/{customer_id}/services",
    tags=[CUSTOMER_SERVICE_CONFIGS_TAG],
    response_model=list[CustomerServiceConfigOut],
    summary="Bulk upsert customer service configs",
    description=(
        "Bulk upsert service configurations for a customer by service_id. "
        "Items omitted from payload remain unchanged."
    ),
    responses={
        200: {"description": "Customer service configs upserted."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
        409: {"description": "Duplicate customer/service configuration is not allowed."},
        422: {"description": "Payload validation failed."},
    },
)
def bulk_upsert_customer_services(
    customer_id: int,
    payload: CustomerServiceConfigBulkUpsertCreate,
    _: object = Depends(require_admin),
    service: CustomerServiceConfigService = Depends(get_customer_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[CustomerServiceConfigOut]:
    rows = service.bulk_upsert(customer_id=customer_id, dto=payload)
    return [
        mapper.to_customer_config_out(config=config, service=service_item, group=group, project=project)
        for config, service_item, group, project in rows
    ]


@router.patch(
    "/customer-service-configs/{config_id}",
    tags=[CUSTOMER_SERVICE_CONFIGS_TAG],
    response_model=CustomerServiceConfigOut,
    summary="Update customer service config",
    description="Update a single customer service config row by id.",
    responses={
        200: {"description": "Customer service config updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer service config not found."},
        422: {"description": "Payload validation failed."},
    },
)
def update_customer_service_config(
    config_id: int,
    payload: CustomerServiceConfigUpdate,
    _: object = Depends(require_admin),
    service: CustomerServiceConfigService = Depends(get_customer_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServiceConfigOut:
    config, service_item, group, project = service.update_single(config_id=config_id, dto=payload)
    return mapper.to_customer_config_out(config=config, service=service_item, group=group, project=project)


@router.delete(
    "/customer-service-configs/{config_id}",
    tags=[CUSTOMER_SERVICE_CONFIGS_TAG],
    response_model=CustomerServiceConfigOut,
    summary="Delete customer service config",
    description="Delete a single customer service config row by id.",
    responses={
        200: {"description": "Customer service config deleted."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer service config not found."},
        409: {"description": "Config is referenced by other records and cannot be deleted."},
    },
)
def delete_customer_service_config(
    config_id: int,
    _: object = Depends(require_admin),
    service: CustomerServiceConfigService = Depends(get_customer_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServiceConfigOut:
    config, service_item, group, project = service.delete_single(config_id=config_id)
    return mapper.to_customer_config_out(config=config, service=service_item, group=group, project=project)


@router.get(
    "/customers/{customer_id}/service-purchases",
    tags=[CUSTOMER_SERVICE_PURCHASES_TAG],
    response_model=CustomerServicePurchaseListOut,
    summary="List customer service purchases",
    description="Return stored service purchases for a customer. Accessible by admin users and the owning customer user.",
    responses={
        200: {"description": "Customer service purchases returned."},
        401: {"description": "Authentication required."},
        403: {"description": "Customer access denied."},
        404: {"description": "Customer not found."},
    },
)
def list_customer_service_purchases(
    response: Response,
    customer_id: int,
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    search: str | None = Query(default=None, description="Search by purchase notes."),
    sort_by: Literal[
        "id",
        "selected_count",
        "sale_total",
        "support_total",
        "grand_total",
        "is_active",
        "created_at",
        "updated_at",
    ] = Query(default="created_at", description="Sort field."),
    sort_order: SortOrder = Query(default=SortOrder.DESC, description="Sort direction."),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user: CurrentUser = Depends(get_current_user),
    service: CustomerServicePurchaseService = Depends(get_customer_service_purchase_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServicePurchaseListOut:
    purchases, meta = service.list_by_customer(
        customer_id=customer_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
        current_user=current_user,
    )
    set_pagination_headers(response=response, meta=meta)
    return CustomerServicePurchaseListOut(
        items=[
            mapper.to_customer_service_purchase_out(
                purchase=item.purchase,
                items=item.items,
            )
            for item in purchases
        ],
        total_page=meta.total_pages,
    )


@router.post(
    "/customers/{customer_id}/service-purchases",
    tags=[CUSTOMER_SERVICE_PURCHASES_TAG],
    response_model=CustomerServicePurchaseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer service purchase",
    description="Create a stored purchase from selected customer service configs. Accessible by admin users and the owning customer user.",
    responses={
        201: {"description": "Customer service purchase created."},
        401: {"description": "Authentication required."},
        403: {"description": "Customer access denied."},
        404: {"description": "Customer not found."},
        422: {"description": "Payload validation failed."},
    },
)
def create_customer_service_purchase(
    customer_id: int,
    payload: CustomerServicePurchaseCreate,
    current_user: CurrentUser = Depends(get_current_user),
    service: CustomerServicePurchaseService = Depends(get_customer_service_purchase_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServicePurchaseOut:
    purchase = service.create(
        customer_id=customer_id,
        dto=payload,
        current_user=current_user,
    )
    return mapper.to_customer_service_purchase_out(
        purchase=purchase.purchase,
        items=purchase.items,
    )


@router.get(
    "/customer-service-purchases/{purchase_id}",
    tags=[CUSTOMER_SERVICE_PURCHASES_TAG],
    response_model=CustomerServicePurchaseOut,
    summary="Get customer service purchase",
    description="Return a stored customer service purchase by id. Accessible by admin users and the owning customer user.",
    responses={
        200: {"description": "Customer service purchase returned."},
        401: {"description": "Authentication required."},
        403: {"description": "Customer access denied."},
        404: {"description": "Customer service purchase not found."},
    },
)
def get_customer_service_purchase(
    purchase_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: CustomerServicePurchaseService = Depends(get_customer_service_purchase_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServicePurchaseOut:
    purchase = service.get_by_id(
        purchase_id=purchase_id,
        current_user=current_user,
    )
    return mapper.to_customer_service_purchase_out(
        purchase=purchase.purchase,
        items=purchase.items,
    )


@router.patch(
    "/customer-service-purchases/{purchase_id}",
    tags=[CUSTOMER_SERVICE_PURCHASES_TAG],
    response_model=CustomerServicePurchaseOut,
    summary="Update customer service purchase",
    description="Update purchase notes or replace the selected customer service configs. Accessible by admin users and the owning customer user.",
    responses={
        200: {"description": "Customer service purchase updated."},
        401: {"description": "Authentication required."},
        403: {"description": "Customer access denied."},
        404: {"description": "Customer service purchase not found."},
        422: {"description": "Payload validation failed."},
    },
)
def update_customer_service_purchase(
    purchase_id: int,
    payload: CustomerServicePurchaseUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: CustomerServicePurchaseService = Depends(get_customer_service_purchase_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServicePurchaseOut:
    purchase = service.update(
        purchase_id=purchase_id,
        dto=payload,
        current_user=current_user,
    )
    return mapper.to_customer_service_purchase_out(
        purchase=purchase.purchase,
        items=purchase.items,
    )


@router.delete(
    "/customer-service-purchases/{purchase_id}",
    tags=[CUSTOMER_SERVICE_PURCHASES_TAG],
    response_model=CustomerServicePurchaseOut,
    summary="Deactivate customer service purchase",
    description="Soft delete a stored customer service purchase by setting is_active=false. Accessible by admin users and the owning customer user.",
    responses={
        200: {"description": "Customer service purchase deactivated."},
        401: {"description": "Authentication required."},
        403: {"description": "Customer access denied."},
        404: {"description": "Customer service purchase not found."},
    },
)
def deactivate_customer_service_purchase(
    purchase_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: CustomerServicePurchaseService = Depends(get_customer_service_purchase_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> CustomerServicePurchaseOut:
    purchase = service.deactivate(
        purchase_id=purchase_id,
        current_user=current_user,
    )
    return mapper.to_customer_service_purchase_out(
        purchase=purchase.purchase,
        items=purchase.items,
    )


@router.get(
    "/customers/{customer_id}/pricing-summary",
    tags=[CUSTOMER_PRICING_TAG],
    response_model=CustomerPricingSummaryResult,
    summary="Get customer pricing summary",
    description="Return customer service configuration and aggregate totals for pricing.",
    responses={
        200: {"description": "Customer pricing summary returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
    },
)
def get_customer_pricing_summary(
    customer_id: int,
    _: object = Depends(require_admin),
    service: CustomerPricingSummaryService = Depends(get_customer_pricing_summary_service),
) -> CustomerPricingSummaryResult:
    return service.get_summary(customer_id=customer_id)
