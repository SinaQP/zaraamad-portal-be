from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.common.enums import SortOrder
from app.common.pagination import PaginationParams, set_pagination_headers
from app.common.security.dependencies import require_admin
from app.modules.customers.dtos import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
)
from app.modules.customers.mappers import CustomerMapper, get_customer_mapper
from app.modules.customers.service import CustomerService, get_customer_service

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post(
    "",
    response_model=CustomerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
    description="Create a new customer. Only admin users can access this endpoint.",
    responses={
        201: {"description": "Customer created."},
        403: {"description": "Admin access required."},
        409: {"description": "Data integrity error."},
    },
)
def create_customer(
    payload: CustomerCreate,
    _: object = Depends(require_admin),
    service: CustomerService = Depends(get_customer_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerOut:
    customer = service.create(dto=payload)
    return mapper.to_out(customer=customer)


@router.get(
    "",
    response_model=list[CustomerOut],
    summary="List customers",
    description="Return customers with optional active-state filtering.",
    responses={
        200: {"description": "Customer list returned."},
        403: {"description": "Admin access required."},
    },
)
def list_customers(
    response: Response,
    is_active: bool | None = Query(default=None, description="Filter by active flag."),
    search: str | None = Query(default=None, description="Search by customer name."),
    sort_by: Literal["id", "name", "grade", "is_active", "created_at", "updated_at"] = Query(
        default="id",
        description="Sort field.",
    ),
    sort_order: SortOrder = Query(default=SortOrder.ASC, description="Sort direction."),
    page: int = Query(default=1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size."),
    _: object = Depends(require_admin),
    service: CustomerService = Depends(get_customer_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> list[CustomerOut]:
    customers, meta = service.list(
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=PaginationParams(page=page, page_size=page_size),
    )
    set_pagination_headers(response=response, meta=meta)
    return [mapper.to_out(customer=item) for item in customers]


@router.get(
    "/{customer_id}",
    response_model=CustomerOut,
    summary="Get customer by id",
    description="Return a customer by its id.",
    responses={
        200: {"description": "Customer returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
    },
)
def get_customer(
    customer_id: int,
    _: object = Depends(require_admin),
    service: CustomerService = Depends(get_customer_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerOut:
    customer = service.get_or_404(customer_id=customer_id)
    return mapper.to_out(customer=customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerOut,
    summary="Update customer",
    description="Partially update a customer by id.",
    responses={
        200: {"description": "Customer updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
        409: {"description": "Data integrity error."},
    },
)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    _: object = Depends(require_admin),
    service: CustomerService = Depends(get_customer_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerOut:
    customer = service.update(customer_id=customer_id, dto=payload)
    return mapper.to_out(customer=customer)


@router.delete(
    "/{customer_id}",
    response_model=CustomerOut,
    summary="Deactivate customer",
    description="Soft delete customer by setting is_active=false.",
    responses={
        200: {"description": "Customer deactivated."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
    },
)
def deactivate_customer(
    customer_id: int,
    _: object = Depends(require_admin),
    service: CustomerService = Depends(get_customer_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerOut:
    customer = service.deactivate(customer_id=customer_id)
    return mapper.to_out(customer=customer)
