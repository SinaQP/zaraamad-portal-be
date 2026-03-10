from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.enums import SortOrder
from app.common.pagination import PaginationParams, set_pagination_headers
from app.common.security.dependencies import require_admin
from app.modules.service_catalog.dtos import (
    MunicipalityPricingSummaryResult,
    MunicipalityServiceConfigBulkUpsertCreate,
    MunicipalityServiceConfigOut,
    MunicipalityServiceConfigUpdate,
    ServiceCreate,
    ServiceGroupCreate,
    ServiceGroupOut,
    ServiceGroupUpdate,
    ServiceOut,
    ServiceProjectCreate,
    ServiceProjectOut,
    ServiceProjectUpdate,
    ServiceUpdate,
)
from app.modules.service_catalog.mappers import ServiceCatalogMapper, get_service_catalog_mapper
from app.modules.service_catalog.service import (
    MunicipalityPricingSummaryService,
    MunicipalityServiceConfigService,
    ServiceCatalogService,
    ServiceGroupService,
    ServiceProjectService,
    get_municipality_pricing_summary_service,
    get_municipality_service_config_service,
    get_service_catalog_service,
    get_service_group_service,
    get_service_project_service,
)

router = APIRouter(tags=["service-catalog"])


@router.post(
    "/service-projects",
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
    response_model=list[ServiceProjectOut],
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
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size."),
    _: object = Depends(require_admin),
    service: ServiceProjectService = Depends(get_service_project_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[ServiceProjectOut]:
    projects, meta = service.list(
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=PaginationParams(page=page, page_size=page_size),
    )
    set_pagination_headers(response=response, meta=meta)
    return [mapper.to_service_project_out(project=item) for item in projects]


@router.get(
    "/service-projects/{project_id}",
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
    project = service.get_or_404(project_id=project_id)
    return mapper.to_service_project_out(project=project)


@router.patch(
    "/service-projects/{project_id}",
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
    response_model=ServiceGroupOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create service group",
    description="Create a new service group under a service project. Only admin users can access this endpoint.",
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
    group, project = service.create(dto=payload)
    return mapper.to_service_group_out(group=group, project=project)


@router.get(
    "/service-groups",
    response_model=list[ServiceGroupOut],
    summary="List service groups",
    description="Return service groups with optional project and active-state filtering.",
    responses={
        200: {"description": "Service group list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_service_groups(
    response: Response,
    project_id: int | None = Query(default=None, description="Filter by service project id."),
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    search: str | None = Query(default=None, description="Search by project name or group code, name, or description."),
    sort_by: Literal[
        "id",
        "project_id",
        "project_sort_order",
        "code",
        "name",
        "sort_order",
        "is_active",
        "created_at",
        "updated_at",
    ] = Query(
        default="project_sort_order",
        description="Sort field.",
    ),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size."),
    _: object = Depends(require_admin),
    service: ServiceGroupService = Depends(get_service_group_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[ServiceGroupOut]:
    groups, meta = service.list(
        project_id=project_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=PaginationParams(page=page, page_size=page_size),
    )
    set_pagination_headers(response=response, meta=meta)
    return [mapper.to_service_group_out(group=item, project=project) for item, project in groups]


@router.get(
    "/service-groups/{group_id}",
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
    group, project = service.get_or_404(group_id=group_id)
    return mapper.to_service_group_out(group=group, project=project)


@router.patch(
    "/service-groups/{group_id}",
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
    group, project = service.update(group_id=group_id, dto=payload)
    return mapper.to_service_group_out(group=group, project=project)


@router.delete(
    "/service-groups/{group_id}",
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
    group, project = service.deactivate(group_id=group_id)
    return mapper.to_service_group_out(group=group, project=project)


@router.post(
    "/services",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create service catalog item",
    description="Create a new global service catalog item. Only admin users can access this endpoint.",
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
    response_model=list[ServiceOut],
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
    search: str | None = Query(default=None, description="Search by project name or group/service code, name, or description."),
    sort_by: Literal[
        "id",
        "project_id",
        "group_id",
        "project_sort_order",
        "group_sort_order",
        "code",
        "name",
        "sort_order",
        "is_active",
        "created_at",
        "updated_at",
    ] = Query(default="project_sort_order", description="Sort field."),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size."),
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[ServiceOut]:
    services, meta = service.list(
        project_id=project_id,
        group_id=group_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=PaginationParams(page=page, page_size=page_size),
    )
    set_pagination_headers(response=response, meta=meta)
    return [mapper.to_service_out(service=item, group=group, project=project) for item, group, project in services]


@router.get(
    "/services/{service_id}",
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
    item, group, project = service.get_or_404(service_id=service_id)
    return mapper.to_service_out(service=item, group=group, project=project)


@router.patch(
    "/services/{service_id}",
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
    "/municipalities/{municipality_id}/services",
    response_model=list[MunicipalityServiceConfigOut],
    summary="List municipality service configs",
    description="Return all configured services for a municipality with project, group, price, and enabled status.",
    responses={
        200: {"description": "Municipality service configs returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality not found."},
    },
)
def list_municipality_services(
    response: Response,
    municipality_id: int,
    project_id: int | None = Query(default=None, description="Filter by service project id."),
    is_enabled: bool | None = Query(default=None, description="Filter by enabled state."),
    search: str | None = Query(default=None, description="Search by project name or group/service code, name, or notes."),
    sort_by: Literal[
        "id",
        "project_id",
        "project_name",
        "project_sort_order",
        "service_id",
        "service_code",
        "service_name",
        "group_code",
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
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size."),
    _: object = Depends(require_admin),
    service: MunicipalityServiceConfigService = Depends(get_municipality_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[MunicipalityServiceConfigOut]:
    rows, meta = service.list_by_municipality(
        municipality_id=municipality_id,
        project_id=project_id,
        is_enabled=is_enabled,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=PaginationParams(page=page, page_size=page_size),
    )
    set_pagination_headers(response=response, meta=meta)
    return [
        mapper.to_municipality_config_out(config=config, service=service_item, group=group, project=project)
        for config, service_item, group, project in rows
    ]


@router.put(
    "/municipalities/{municipality_id}/services",
    response_model=list[MunicipalityServiceConfigOut],
    summary="Bulk upsert municipality service configs",
    description=(
        "Bulk upsert service configurations for a municipality by service_id. "
        "Items omitted from payload remain unchanged."
    ),
    responses={
        200: {"description": "Municipality service configs upserted."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality not found."},
        409: {"description": "Duplicate municipality/service configuration is not allowed."},
        422: {"description": "Payload validation failed."},
    },
)
def bulk_upsert_municipality_services(
    municipality_id: int,
    payload: MunicipalityServiceConfigBulkUpsertCreate,
    _: object = Depends(require_admin),
    service: MunicipalityServiceConfigService = Depends(get_municipality_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[MunicipalityServiceConfigOut]:
    rows = service.bulk_upsert(municipality_id=municipality_id, dto=payload)
    return [
        mapper.to_municipality_config_out(config=config, service=service_item, group=group, project=project)
        for config, service_item, group, project in rows
    ]


@router.patch(
    "/municipality-service-configs/{config_id}",
    response_model=MunicipalityServiceConfigOut,
    summary="Update municipality service config",
    description="Update a single municipality service config row by id.",
    responses={
        200: {"description": "Municipality service config updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality service config not found."},
        422: {"description": "Payload validation failed."},
    },
)
def update_municipality_service_config(
    config_id: int,
    payload: MunicipalityServiceConfigUpdate,
    _: object = Depends(require_admin),
    service: MunicipalityServiceConfigService = Depends(get_municipality_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> MunicipalityServiceConfigOut:
    config, service_item, group, project = service.update_single(config_id=config_id, dto=payload)
    return mapper.to_municipality_config_out(config=config, service=service_item, group=group, project=project)


@router.get(
    "/municipalities/{municipality_id}/pricing-summary",
    response_model=MunicipalityPricingSummaryResult,
    summary="Get municipality pricing summary",
    description="Return municipality service configuration and aggregate totals for pricing.",
    responses={
        200: {"description": "Municipality pricing summary returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality not found."},
    },
)
def get_municipality_pricing_summary(
    municipality_id: int,
    _: object = Depends(require_admin),
    service: MunicipalityPricingSummaryService = Depends(get_municipality_pricing_summary_service),
) -> MunicipalityPricingSummaryResult:
    return service.get_summary(municipality_id=municipality_id)
