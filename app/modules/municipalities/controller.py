from fastapi import APIRouter, Depends, Query, status

from app.common.security.dependencies import require_admin
from app.modules.municipalities.dtos import (
    MunicipalityCreate,
    MunicipalityOut,
    MunicipalityUpdate,
)
from app.modules.municipalities.mappers import MunicipalityMapper, get_municipality_mapper
from app.modules.municipalities.service import MunicipalityService, get_municipality_service

router = APIRouter(prefix="/municipalities", tags=["municipalities"])


@router.post(
    "",
    response_model=MunicipalityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create municipality",
    description="Create a new municipality. Only admin users can access this endpoint.",
    responses={
        201: {"description": "Municipality created."},
        403: {"description": "Admin access required."},
        409: {"description": "Municipality code already exists."},
    },
)
def create_municipality(
    payload: MunicipalityCreate,
    _: object = Depends(require_admin),
    service: MunicipalityService = Depends(get_municipality_service),
    mapper: MunicipalityMapper = Depends(get_municipality_mapper),
) -> MunicipalityOut:
    municipality = service.create(dto=payload)
    return mapper.to_out(municipality=municipality)


@router.get(
    "",
    response_model=list[MunicipalityOut],
    summary="List municipalities",
    description="Return municipalities with optional active-state filtering.",
    responses={
        200: {"description": "Municipality list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_municipalities(
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    _: object = Depends(require_admin),
    service: MunicipalityService = Depends(get_municipality_service),
    mapper: MunicipalityMapper = Depends(get_municipality_mapper),
) -> list[MunicipalityOut]:
    municipalities = service.list(is_active=is_active)
    return [mapper.to_out(municipality=item) for item in municipalities]


@router.get(
    "/{municipality_id}",
    response_model=MunicipalityOut,
    summary="Get municipality by id",
    description="Return a municipality by its id.",
    responses={
        200: {"description": "Municipality returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality not found."},
    },
)
def get_municipality(
    municipality_id: int,
    _: object = Depends(require_admin),
    service: MunicipalityService = Depends(get_municipality_service),
    mapper: MunicipalityMapper = Depends(get_municipality_mapper),
) -> MunicipalityOut:
    municipality = service.get_or_404(municipality_id=municipality_id)
    return mapper.to_out(municipality=municipality)


@router.patch(
    "/{municipality_id}",
    response_model=MunicipalityOut,
    summary="Update municipality",
    description="Partially update a municipality by id.",
    responses={
        200: {"description": "Municipality updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality not found."},
        409: {"description": "Municipality code already exists."},
    },
)
def update_municipality(
    municipality_id: int,
    payload: MunicipalityUpdate,
    _: object = Depends(require_admin),
    service: MunicipalityService = Depends(get_municipality_service),
    mapper: MunicipalityMapper = Depends(get_municipality_mapper),
) -> MunicipalityOut:
    municipality = service.update(municipality_id=municipality_id, dto=payload)
    return mapper.to_out(municipality=municipality)


@router.delete(
    "/{municipality_id}",
    response_model=MunicipalityOut,
    summary="Deactivate municipality",
    description="Soft delete municipality by setting is_active=false.",
    responses={
        200: {"description": "Municipality deactivated."},
        403: {"description": "Admin access required."},
        404: {"description": "Municipality not found."},
    },
)
def deactivate_municipality(
    municipality_id: int,
    _: object = Depends(require_admin),
    service: MunicipalityService = Depends(get_municipality_service),
    mapper: MunicipalityMapper = Depends(get_municipality_mapper),
) -> MunicipalityOut:
    municipality = service.deactivate(municipality_id=municipality_id)
    return mapper.to_out(municipality=municipality)
