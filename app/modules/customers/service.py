from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.common.database import get_db_session
from app.common.enums import SortOrder
from app.common.messages import (
    CUSTOMER_BRIDGE_AUTH_FAILED,
    CUSTOMER_BRIDGE_INVALID_RESPONSE,
    CUSTOMER_BRIDGE_NOT_CONFIGURED,
    CUSTOMER_BRIDGE_REQUEST_FAILED,
    CUSTOMER_BRIDGE_UNAVAILABLE,
    CUSTOMER_NOT_FOUND,
    DATA_INTEGRITY_ERROR,
)
from app.common.pagination import PaginationMeta, PaginationParams
from app.common.services.bridge_client import (
    BridgeCapabilitiesResult,
    BridgeClient,
    BridgeConnectionError,
    BridgeHealthResult,
    BridgeInvalidResponseError,
    BridgeRequest,
    BridgeUnauthorizedError,
    BridgeUnexpectedStatusError,
    get_bridge_client,
)
from app.modules.customers.dtos import CustomerCreate, CustomerUpdate
from app.modules.customers.schemas import Customer


class CustomerQueryBuilder:
    SORT_COLUMNS = {
        "id": Customer.id,
        "name": Customer.name,
        "grade": Customer.grade,
        "is_active": Customer.is_active,
        "created_at": Customer.created_at,
        "updated_at": Customer.updated_at,
    }

    def build_list_query(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Customer]]:
        query = select(Customer)
        if is_active is not None:
            query = query.where(Customer.is_active.is_(is_active))
        if search:
            query = query.where(Customer.name.ilike(f"%{search}%"))
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), Customer.id.desc())
        else:
            query = query.order_by(sort_column.asc(), Customer.id.asc())
        return query


class CustomerService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = CustomerQueryBuilder()

    def create(self, dto: CustomerCreate) -> Customer:
        customer = Customer(
            name=dto.name,
            grade=dto.grade,
            is_active=True,
            bridge_base_url=dto.bridge_base_url,
            bridge_api_key=dto.bridge_api_key,
            bridge_is_enabled=dto.bridge_is_enabled,
        )
        self._db_session.add(customer)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(customer)
        return customer

    def list(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[Customer], PaginationMeta]:
        query = self._query_builder.build_list_query(
            is_active=is_active,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total_count = int(
            self._db_session.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            ) or 0
        )
        paginated_query = query.offset(pagination.offset).limit(pagination.page_size)
        items = list(self._db_session.scalars(paginated_query).all())
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def list_all(self) -> list[Customer]:
        query = select(Customer).order_by(Customer.id.asc())
        return list(self._db_session.scalars(query).all())

    def get_or_404(self, customer_id: int) -> Customer:
        customer = self._db_session.get(Customer, customer_id)
        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_NOT_FOUND,
            )
        return customer

    def update(self, customer_id: int, dto: CustomerUpdate) -> Customer:
        customer = self.get_or_404(customer_id=customer_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(customer, field_name, field_value)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(customer)
        return customer

    def deactivate(self, customer_id: int) -> Customer:
        customer = self.get_or_404(customer_id=customer_id)
        customer.is_active = False
        self._db_session.commit()
        self._db_session.refresh(customer)
        return customer


@dataclass(frozen=True)
class ResolvedCustomerBridgeConfig:
    base_url: str
    api_key: str
    timeout_seconds: int


class CustomerBridgeConfigResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(self, customer: Customer) -> ResolvedCustomerBridgeConfig:
        missing_fields: list[str] = []
        if not customer.bridge_is_enabled:
            missing_fields.append("bridge_is_enabled")
        if not customer.bridge_base_url:
            missing_fields.append("bridge_base_url")
        if not customer.bridge_api_key:
            missing_fields.append("bridge_api_key")
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": CUSTOMER_BRIDGE_NOT_CONFIGURED,
                    "developer_message": (
                        f"Customer {customer.id} bridge configuration is incomplete. "
                        f"Missing or disabled fields: {', '.join(missing_fields)}."
                    ),
                },
            )
        return ResolvedCustomerBridgeConfig(
            base_url=customer.bridge_base_url,
            api_key=customer.bridge_api_key,
            timeout_seconds=self._settings.bridge_request_timeout_seconds,
        )


class CustomerBridgeService:
    def __init__(
        self,
        customer_service: CustomerService,
        bridge_client: BridgeClient,
        settings: Settings,
    ) -> None:
        self._customer_service = customer_service
        self._bridge_client = bridge_client
        self._config_resolver = CustomerBridgeConfigResolver(settings=settings)

    def get_health(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, BridgeHealthResult]:
        customer, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        try:
            bridge_health = self._bridge_client.get_health(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            raise self._map_bridge_error(customer=customer, exc=exc) from exc
        return customer, bridge_health

    def get_capabilities(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, BridgeCapabilitiesResult]:
        customer, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        try:
            bridge_capabilities = self._bridge_client.get_capabilities(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            raise self._map_bridge_error(customer=customer, exc=exc) from exc
        return customer, bridge_capabilities

    def _build_request(
        self,
        customer_id: int,
        correlation_id: str | None,
    ) -> tuple[Customer, BridgeRequest]:
        customer = self._customer_service.get_or_404(customer_id=customer_id)
        bridge_config = self._config_resolver.resolve(customer=customer)
        return customer, BridgeRequest(
            base_url=bridge_config.base_url,
            api_key=bridge_config.api_key,
            timeout_seconds=bridge_config.timeout_seconds,
            correlation_id=correlation_id,
        )

    def _map_bridge_error(
        self,
        customer: Customer,
        exc: (
            BridgeConnectionError
            | BridgeUnauthorizedError
            | BridgeUnexpectedStatusError
            | BridgeInvalidResponseError
        ),
    ) -> HTTPException:
        if isinstance(exc, BridgeConnectionError):
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": CUSTOMER_BRIDGE_UNAVAILABLE,
                    "developer_message": (
                        f"Bridge request for customer {customer.id} could not reach "
                        f"{customer.bridge_base_url}: {exc}"
                    ),
                },
            )
        if isinstance(exc, BridgeUnauthorizedError):
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": CUSTOMER_BRIDGE_AUTH_FAILED,
                    "developer_message": (
                        f"Bridge request for customer {customer.id} was rejected with "
                        f"status {exc.status_code}."
                    ),
                },
            )
        if isinstance(exc, BridgeUnexpectedStatusError):
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": CUSTOMER_BRIDGE_REQUEST_FAILED,
                    "developer_message": (
                        f"Bridge request for customer {customer.id} returned "
                        f"unexpected status {exc.status_code}."
                    ),
                },
            )
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": CUSTOMER_BRIDGE_INVALID_RESPONSE,
                "developer_message": (
                    f"Bridge response for customer {customer.id} did not match the "
                    f"expected schema: {exc}"
                ),
            },
        )


def get_customer_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerService:
    return CustomerService(db_session=db_session)


def get_customer_bridge_service(
    customer_service: CustomerService = Depends(get_customer_service),
    bridge_client: BridgeClient = Depends(get_bridge_client),
    settings: Settings = Depends(get_settings),
) -> CustomerBridgeService:
    return CustomerBridgeService(
        customer_service=customer_service,
        bridge_client=bridge_client,
        settings=settings,
    )
