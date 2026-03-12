from fastapi import APIRouter, Depends, status

from app.common.security.dependencies import RequestAccessContext, require_admin_or_bridge_access
from app.modules.subscriptions.dtos import (
    SubscriptionCreate,
    SubscriptionMessageCreate,
    SubscriptionMessageOut,
    SubscriptionOut,
    SubscriptionUpdate,
)
from app.modules.subscriptions.mappers import SubscriptionMapper, get_subscription_mapper
from app.modules.subscriptions.service import SubscriptionService, get_subscription_service

SUBSCRIPTIONS_TAG = "subscriptions"

router = APIRouter(prefix="/sub")


@router.post(
    "/subscription/",
    tags=[SUBSCRIPTIONS_TAG],
    response_model=SubscriptionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create active subscription",
    description="Create a new active subscription and deactivate the previous active subscription if one exists.",
    responses={
        201: {"description": "Active subscription created."},
        401: {"description": "Admin token or bridge key is required."},
        403: {"description": "Admin access required for application requests."},
        409: {"description": "Data integrity error."},
    },
)
def create_active_subscription(
    payload: SubscriptionCreate,
    _: RequestAccessContext = Depends(require_admin_or_bridge_access),
    service: SubscriptionService = Depends(get_subscription_service),
    mapper: SubscriptionMapper = Depends(get_subscription_mapper),
) -> SubscriptionOut:
    subscription = service.create_active(dto=payload)
    return mapper.to_subscription_out(subscription=subscription)


@router.get(
    "/subscriptions/active/",
    tags=[SUBSCRIPTIONS_TAG],
    response_model=SubscriptionOut,
    summary="Get active subscription",
    description="Return the current active subscription.",
    responses={
        200: {"description": "Active subscription returned."},
        401: {"description": "Admin token or bridge key is required."},
        403: {"description": "Admin access required for application requests."},
        404: {"description": "Active subscription not found."},
    },
)
def get_active_subscription(
    _: RequestAccessContext = Depends(require_admin_or_bridge_access),
    service: SubscriptionService = Depends(get_subscription_service),
    mapper: SubscriptionMapper = Depends(get_subscription_mapper),
) -> SubscriptionOut:
    subscription = service.get_active()
    return mapper.to_subscription_out(subscription=subscription)


@router.patch(
    "/subscriptions/active/",
    tags=[SUBSCRIPTIONS_TAG],
    response_model=SubscriptionOut,
    summary="Update active subscription",
    description="Partially update the current active subscription, or create one when no active subscription exists and the request provides enough data.",
    responses={
        200: {"description": "Active subscription updated."},
        401: {"description": "Admin token or bridge key is required."},
        403: {"description": "Admin access required for application requests."},
        409: {"description": "Data integrity error."},
        422: {"description": "Request payload is incomplete."},
    },
)
def update_active_subscription(
    payload: SubscriptionUpdate,
    _: RequestAccessContext = Depends(require_admin_or_bridge_access),
    service: SubscriptionService = Depends(get_subscription_service),
    mapper: SubscriptionMapper = Depends(get_subscription_mapper),
) -> SubscriptionOut:
    subscription = service.update_active(dto=payload)
    return mapper.to_subscription_out(subscription=subscription)


@router.get(
    "/subscriptions/messages/",
    tags=[SUBSCRIPTIONS_TAG],
    response_model=list[SubscriptionMessageOut],
    summary="List subscription messages",
    description="Return the stored subscription message templates.",
    responses={
        200: {"description": "Subscription message templates returned."},
        401: {"description": "Admin token or bridge key is required."},
        403: {"description": "Admin access required for application requests."},
    },
)
def list_subscription_messages(
    _: RequestAccessContext = Depends(require_admin_or_bridge_access),
    service: SubscriptionService = Depends(get_subscription_service),
    mapper: SubscriptionMapper = Depends(get_subscription_mapper),
) -> list[SubscriptionMessageOut]:
    messages = service.list_messages()
    return [
        mapper.to_subscription_message_out(subscription_message=item)
        for item in messages
    ]


@router.patch(
    "/subscriptions/messages/",
    tags=[SUBSCRIPTIONS_TAG],
    response_model=list[SubscriptionMessageOut],
    summary="Upsert subscription messages",
    description="Bulk upsert subscription message templates by status.",
    responses={
        200: {"description": "Subscription message templates upserted."},
        401: {"description": "Admin token or bridge key is required."},
        403: {"description": "Admin access required for application requests."},
        409: {"description": "Data integrity error."},
        422: {"description": "Request payload is invalid."},
    },
)
def upsert_subscription_messages(
    payload: list[SubscriptionMessageCreate],
    _: RequestAccessContext = Depends(require_admin_or_bridge_access),
    service: SubscriptionService = Depends(get_subscription_service),
    mapper: SubscriptionMapper = Depends(get_subscription_mapper),
) -> list[SubscriptionMessageOut]:
    messages = service.upsert_messages(dtos=payload)
    return [
        mapper.to_subscription_message_out(subscription_message=item)
        for item in messages
    ]
