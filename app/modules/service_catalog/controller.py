from fastapi import APIRouter, Depends, Query, status

from app.common.security.dependencies import require_admin
from app.modules.service_catalog.dtos import (
    MunicipalityPricingSummaryResult,
    MunicipalityServiceConfigBulkUpsertCreate,
    MunicipalityServiceConfigOut,
    MunicipalityServiceConfigUpdate,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
)
from app.modules.service_catalog.mappers import ServiceCatalogMapper, get_service_catalog_mapper
from app.modules.service_catalog.service import (
    MunicipalityPricingSummaryService,
    MunicipalityServiceConfigService,
    ServiceCatalogService,
    get_municipality_pricing_summary_service,
    get_municipality_service_config_service,
    get_service_catalog_service,
)

router = APIRouter(tags=["service-catalog"])


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
    created_service = service.create(dto=payload)
    return mapper.to_service_out(service=created_service)


@router.get(
    "/services",
    response_model=list[ServiceOut],
    summary="List service catalog items",
    description="Return global services with optional active-state filtering.",
    responses={
        200: {"description": "Service list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_services(
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    _: object = Depends(require_admin),
    service: ServiceCatalogService = Depends(get_service_catalog_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[ServiceOut]:
    services = service.list(is_active=is_active)
    return [mapper.to_service_out(service=item) for item in services]


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
    item = service.get_or_404(service_id=service_id)
    return mapper.to_service_out(service=item)


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
    updated_service = service.update(service_id=service_id, dto=payload)
    return mapper.to_service_out(service=updated_service)


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
    deactivated_service = service.deactivate(service_id=service_id)
    return mapper.to_service_out(service=deactivated_service)


@router.get(
    "/municipalities/{municipality_id}/services",
    response_model=list[MunicipalityServiceConfigOut],
    summary="List municipality service configs",
    description="Return all configured services for a municipality with price and enabled status.",
    responses={
        200: {"description": "Municipality service configs returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality not found."},
    },
)
def list_municipality_services(
    municipality_id: int,
    _: object = Depends(require_admin),
    service: MunicipalityServiceConfigService = Depends(get_municipality_service_config_service),
    mapper: ServiceCatalogMapper = Depends(get_service_catalog_mapper),
) -> list[MunicipalityServiceConfigOut]:
    rows = service.list_by_municipality(municipality_id=municipality_id)
    return [
        mapper.to_municipality_config_out(config=config, service=service_item)
        for config, service_item in rows
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
        mapper.to_municipality_config_out(config=config, service=service_item)
        for config, service_item in rows
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
    config, service_item = service.update_single(config_id=config_id, dto=payload)
    return mapper.to_municipality_config_out(config=config, service=service_item)


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
