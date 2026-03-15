from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.common.enums import SortOrder
from app.common.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.common.security.dependencies import require_admin
from app.modules.customers.dtos import (
    CustomerBridgeCapabilitiesOut,
    CustomerBridgeConfigOut,
    CustomerBridgeConfigUpdate,
    CustomerBridgeHealthOut,
    CustomerBridgeSubscriptionOut,
    CustomerCreate,
    CustomerListOut,
    CustomerOut,
    CustomerUpdate,
)
from app.modules.customers.mappers import CustomerMapper, get_customer_mapper
from app.modules.customers.service import (
    CustomerBridgeService,
    CustomerBridgeConfigService,
    CustomerService,
    get_customer_bridge_service,
    get_customer_bridge_config_service,
    get_customer_service,
)
from app.modules.subscriptions.dtos import (
    BridgeSubscriptionConfigOut,
    BridgeSubscriptionConfigUpdate,
    BridgeSubscriptionMessageOut,
    BridgeSubscriptionMessageUpdate,
    BridgeSubscriptionOut,
    BridgeSubscriptionUpdate,
)
from app.modules.subscriptions.mappers import (
    SubscriptionBridgeMapper,
    get_subscription_bridge_mapper,
)

CUSTOMERS_TAG = "customers"
CUSTOMER_BRIDGE_TAG = "customer-bridge"

router = APIRouter(prefix="/customers")


@router.post(
    "",
    tags=[CUSTOMERS_TAG],
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
    tags=[CUSTOMERS_TAG],
    response_model=CustomerListOut,
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
    pagination: PaginationParams = Depends(get_pagination_params),
    _: object = Depends(require_admin),
    service: CustomerService = Depends(get_customer_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerListOut:
    customers, meta = service.list_customers(
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )
    set_pagination_headers(response=response, meta=meta)
    return CustomerListOut(
        items=[mapper.to_out(customer=item) for item in customers],
        total_page=meta.total_pages,
    )


@router.get(
    "/all",
    tags=[CUSTOMERS_TAG],
    response_model=list[CustomerOut],
    summary="Get all customers",
    description="Return all customers without filters, search, sorting, or pagination.",
    responses={
        200: {"description": "All customers returned."},
        403: {"description": "Admin access required."},
    },
)
def get_all_customers(
    _: object = Depends(require_admin),
    service: CustomerService = Depends(get_customer_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> list[CustomerOut]:
    customers = service.list_all()
    return [mapper.to_out(customer=item) for item in customers]


@router.get(
    "/{customer_id}",
    tags=[CUSTOMERS_TAG],
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
    customer = service.get_active_or_404(customer_id=customer_id)
    return mapper.to_out(customer=customer)


@router.patch(
    "/{customer_id}",
    tags=[CUSTOMERS_TAG],
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
    tags=[CUSTOMERS_TAG],
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


@router.get(
    "/{customer_id}/bridge",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=CustomerBridgeConfigOut,
    summary="Get customer bridge config",
    description="Return the current bridge configuration view for a customer.",
    responses={
        200: {"description": "Customer bridge configuration returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
    },
)
def get_customer_bridge_config(
    customer_id: int,
    _: object = Depends(require_admin),
    service: CustomerBridgeConfigService = Depends(get_customer_bridge_config_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerBridgeConfigOut:
    customer, bridge_config = service.get_active(customer_id=customer_id)
    return mapper.to_bridge_config_out(
        customer=customer,
        bridge_config=bridge_config,
    )


@router.post(
    "/{customer_id}/bridge/refresh-status",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=CustomerBridgeConfigOut,
    summary="Refresh customer bridge status",
    description="Run a live bridge health check, update cached bridge status fields, and return the latest cached status view.",
    responses={
        200: {"description": "Customer bridge status refreshed."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
        409: {"description": "Customer bridge configuration is incomplete."},
    },
)
def refresh_customer_bridge_status(
    customer_id: int,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerBridgeConfigOut:
    customer, bridge_config = service.refresh_status(
        customer_id=customer_id,
        correlation_id=x_correlation_id,
    )
    return mapper.to_bridge_config_out(
        customer=customer,
        bridge_config=bridge_config,
    )


@router.patch(
    "/{customer_id}/bridge",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=CustomerBridgeConfigOut,
    summary="Update customer bridge config",
    description="Create or partially update the stored bridge configuration for a customer.",
    responses={
        200: {"description": "Customer bridge configuration updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
        409: {"description": "Data integrity error."},
    },
)
def update_customer_bridge_config(
    customer_id: int,
    payload: CustomerBridgeConfigUpdate,
    _: object = Depends(require_admin),
    service: CustomerBridgeConfigService = Depends(get_customer_bridge_config_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerBridgeConfigOut:
    customer, bridge_config = service.upsert(
        customer_id=customer_id,
        dto=payload,
    )
    return mapper.to_bridge_config_out(
        customer=customer,
        bridge_config=bridge_config,
    )


@router.get(
    "/{customer_id}/bridge/health",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=CustomerBridgeHealthOut,
    summary="Get customer bridge health",
    description="Call the configured municipality bridge health endpoint for a customer.",
    responses={
        200: {"description": "Customer bridge health returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
        409: {"description": "Customer bridge configuration is incomplete."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def get_customer_bridge_health(
    customer_id: int,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerBridgeHealthOut:
    customer, bridge_config, bridge_health = service.get_health(
        customer_id=customer_id,
        correlation_id=x_correlation_id,
    )
    return mapper.to_bridge_health_out(
        customer=customer,
        bridge_config=bridge_config,
        bridge_health=bridge_health,
    )


@router.get(
    "/{customer_id}/bridge/capabilities",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=CustomerBridgeCapabilitiesOut,
    summary="Get customer bridge capabilities",
    description="Call the configured municipality bridge capabilities endpoint for a customer.",
    responses={
        200: {"description": "Customer bridge capabilities returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found."},
        409: {"description": "Customer bridge configuration is incomplete."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def get_customer_bridge_capabilities(
    customer_id: int,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerBridgeCapabilitiesOut:
    customer, bridge_config, bridge_capabilities = service.get_capabilities(
        customer_id=customer_id,
        correlation_id=x_correlation_id,
    )
    return mapper.to_bridge_capabilities_out(
        customer=customer,
        bridge_config=bridge_config,
        bridge_capabilities=bridge_capabilities,
    )


@router.get(
    "/{customer_id}/bridge/subscriptions/active",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=BridgeSubscriptionOut,
    summary="Get customer bridge subscription",
    description="Call the configured main app subscription endpoint for a customer.",
    responses={
        200: {"description": "Customer bridge subscription returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found or no active upstream subscription exists."},
        409: {"description": "Customer bridge configuration is incomplete."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def get_customer_bridge_subscription(
    customer_id: int,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: SubscriptionBridgeMapper = Depends(get_subscription_bridge_mapper),
) -> BridgeSubscriptionOut:
    _, _, bridge_subscription = service.fetch_active_subscription(
        customer_id=customer_id,
        correlation_id=x_correlation_id,
    )
    return mapper.to_subscription_out(
        subscription=bridge_subscription,
    )


@router.patch(
    "/{customer_id}/bridge/subscriptions/active",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=BridgeSubscriptionOut,
    summary="Update customer bridge subscription",
    description="Update the active subscription through the configured customer bridge.",
    responses={
        200: {"description": "Customer bridge subscription updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found or no active upstream subscription exists."},
        409: {"description": "Customer bridge configuration is incomplete."},
        422: {"description": "Request payload is incomplete or invalid."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def update_customer_bridge_subscription(
    customer_id: int,
    payload: BridgeSubscriptionUpdate,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: SubscriptionBridgeMapper = Depends(get_subscription_bridge_mapper),
) -> BridgeSubscriptionOut:
    _, _, bridge_subscription = service.update_bridge_subscription(
        customer_id=customer_id,
        payload=payload.model_dump(mode="json", exclude_unset=True, exclude_none=False),
        correlation_id=x_correlation_id,
    )
    return mapper.to_subscription_out(
        subscription=bridge_subscription,
    )


@router.get(
    "/{customer_id}/bridge/subscriptions/messages",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=list[BridgeSubscriptionMessageOut],
    summary="Get customer bridge subscription messages",
    description="Return subscription message templates from the configured customer bridge.",
    responses={
        200: {"description": "Customer bridge subscription messages returned."},
        403: {"description": "Admin access required."},
        409: {"description": "Customer bridge configuration is incomplete."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def get_customer_bridge_subscription_messages(
    customer_id: int,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: SubscriptionBridgeMapper = Depends(get_subscription_bridge_mapper),
) -> list[BridgeSubscriptionMessageOut]:
    _, _, bridge_messages = service.get_subscription_messages(
        customer_id=customer_id,
        correlation_id=x_correlation_id,
    )
    return mapper.to_messages_out(messages=bridge_messages)


@router.patch(
    "/{customer_id}/bridge/subscriptions/messages",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=list[BridgeSubscriptionMessageOut],
    summary="Update customer bridge subscription messages",
    description="Create or update subscription message templates through the configured customer bridge.",
    responses={
        200: {"description": "Customer bridge subscription messages updated."},
        403: {"description": "Admin access required."},
        409: {"description": "Customer bridge configuration is incomplete."},
        422: {"description": "Request payload is invalid."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def update_customer_bridge_subscription_messages(
    customer_id: int,
    payload: list[BridgeSubscriptionMessageUpdate],
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: SubscriptionBridgeMapper = Depends(get_subscription_bridge_mapper),
) -> list[BridgeSubscriptionMessageOut]:
    _, _, bridge_messages = service.upsert_subscription_messages(
        customer_id=customer_id,
        payload=[item.model_dump(mode="json") for item in payload],
        correlation_id=x_correlation_id,
    )
    return mapper.to_messages_out(messages=bridge_messages)


@router.get(
    "/{customer_id}/bridge/subscriptions/config",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=BridgeSubscriptionConfigOut,
    summary="Get customer bridge subscription config",
    description="Return the combined subscription and message config from the configured customer bridge.",
    responses={
        200: {"description": "Customer bridge subscription config returned."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found or no active upstream subscription exists."},
        409: {"description": "Customer bridge configuration is incomplete."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def get_customer_bridge_subscription_config(
    customer_id: int,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: SubscriptionBridgeMapper = Depends(get_subscription_bridge_mapper),
) -> BridgeSubscriptionConfigOut:
    _, _, bridge_config_result = service.get_subscription_config(
        customer_id=customer_id,
        correlation_id=x_correlation_id,
    )
    return mapper.to_config_out(config=bridge_config_result)


@router.patch(
    "/{customer_id}/bridge/subscriptions/config",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=BridgeSubscriptionConfigOut,
    summary="Sync customer bridge subscription config",
    description="Atomically update the active subscription and/or message templates through the configured customer bridge.",
    responses={
        200: {"description": "Customer bridge subscription config updated."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found or no active upstream subscription exists."},
        409: {"description": "Customer bridge configuration is incomplete."},
        422: {"description": "Request payload is incomplete or invalid."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def sync_customer_bridge_subscription_config(
    customer_id: int,
    payload: BridgeSubscriptionConfigUpdate,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: SubscriptionBridgeMapper = Depends(get_subscription_bridge_mapper),
) -> BridgeSubscriptionConfigOut:
    _, _, bridge_config_result = service.sync_subscription_config(
        customer_id=customer_id,
        payload=payload.model_dump(mode="json", exclude_unset=True, exclude_none=False),
        correlation_id=x_correlation_id,
    )
    return mapper.to_config_out(
        config=bridge_config_result,
    )


@router.post(
    "/{customer_id}/bridge/subscriptions/refresh",
    tags=[CUSTOMER_BRIDGE_TAG],
    response_model=CustomerBridgeSubscriptionOut,
    summary="Refresh customer bridge subscription",
    description="Fetch the latest subscription snapshot from the configured main app and store it locally for future reads.",
    responses={
        200: {"description": "Customer bridge subscription refreshed and cached."},
        403: {"description": "Admin access required."},
        404: {"description": "Customer not found or no active upstream subscription exists."},
        409: {"description": "Customer bridge configuration is incomplete."},
        502: {"description": "Customer bridge returned an invalid or unauthorized response."},
        503: {"description": "Customer bridge is unreachable."},
    },
)
def refresh_customer_bridge_subscription(
    customer_id: int,
    x_correlation_id: str | None = Header(
        default=None,
        alias="X-Correlation-ID",
        description="Optional correlation id forwarded to the customer bridge.",
    ),
    _: object = Depends(require_admin),
    service: CustomerBridgeService = Depends(get_customer_bridge_service),
    mapper: CustomerMapper = Depends(get_customer_mapper),
) -> CustomerBridgeSubscriptionOut:
    customer, bridge_config = service.refresh_subscription(
        customer_id=customer_id,
        correlation_id=x_correlation_id,
    )
    return mapper.to_bridge_subscription_out(
        customer=customer,
        bridge_config=bridge_config,
    )
