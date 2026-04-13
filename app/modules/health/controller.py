from fastapi import APIRouter, Depends, Response, status

from app.modules.health.dtos import HealthStatusOut
from app.modules.health.service import HealthService, get_health_service

router = APIRouter(prefix="/health", tags=["health"])

_SUCCESS_STATUSES = {"online", "degraded"}


@router.get(
    "",
    response_model=HealthStatusOut,
    summary="Get API health status",
    description="Return connectivity status for the primary PostgreSQL database and the optional SQL Server connection.",
    responses={
        200: {"description": "Health status returned."},
        503: {"description": "Primary database is offline."},
    },
)
def get_health_status(
    response: Response,
    service: HealthService = Depends(get_health_service),
) -> HealthStatusOut:
    health_status = service.get_status()
    if health_status.status not in _SUCCESS_STATUSES:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health_status
