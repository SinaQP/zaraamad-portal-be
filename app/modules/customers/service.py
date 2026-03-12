from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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
from app.modules.customers.dtos import CustomerBridgeConfigUpdate, CustomerCreate, CustomerUpdate
from app.modules.customers.schemas import Customer, CustomerBridgeConfig


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

    def list_customers(
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


class CustomerBridgeConfigService:
    def __init__(
        self,
        db_session: Session,
        customer_service: CustomerService,
    ) -> None:
        self._db_session = db_session
        self._customer_service = customer_service

    def get(self, customer_id: int) -> tuple[Customer, CustomerBridgeConfig | None]:
        customer = self._customer_service.get_or_404(customer_id=customer_id)
        bridge_config = self._db_session.get(CustomerBridgeConfig, customer_id)
        return customer, bridge_config

    def upsert(
        self,
        customer_id: int,
        dto: CustomerBridgeConfigUpdate,
    ) -> tuple[Customer, CustomerBridgeConfig]:
        customer, bridge_config = self.get(customer_id=customer_id)
        if bridge_config is None:
            bridge_config = CustomerBridgeConfig(customer_id=customer_id)
            self._db_session.add(bridge_config)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(bridge_config, field_name, field_value)
        if update_data:
            self.clear_health_status(bridge_config=bridge_config)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(bridge_config)
        return customer, bridge_config

    def clear_health_status(self, bridge_config: CustomerBridgeConfig) -> None:
        bridge_config.last_online_status = None
        bridge_config.last_health_checked_at = None
        bridge_config.last_health_error = None

    def persist_health_status(
        self,
        bridge_config: CustomerBridgeConfig,
        *,
        is_online: bool,
        checked_at: datetime,
        error: str | None,
    ) -> CustomerBridgeConfig:
        bridge_config.last_online_status = is_online
        bridge_config.last_health_checked_at = checked_at
        bridge_config.last_health_error = error
        self._db_session.commit()
        self._db_session.refresh(bridge_config)
        return bridge_config

    def list_refreshable_customer_ids(self) -> list[int]:
        query = (
            select(CustomerBridgeConfig.customer_id)
            .where(CustomerBridgeConfig.bridge_is_enabled.is_(True))
            .where(CustomerBridgeConfig.bridge_base_url.is_not(None))
            .where(CustomerBridgeConfig.bridge_base_url != "")
            .where(CustomerBridgeConfig.bridge_api_key.is_not(None))
            .where(CustomerBridgeConfig.bridge_api_key != "")
            .order_by(CustomerBridgeConfig.customer_id.asc())
        )
        return list(self._db_session.scalars(query).all())


@dataclass(frozen=True)
class ResolvedCustomerBridgeConfig:
    base_url: str
    api_key: str
    timeout_seconds: int


class CustomerBridgeConfigResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(
        self,
        customer: Customer,
        bridge_config: CustomerBridgeConfig | None,
    ) -> ResolvedCustomerBridgeConfig:
        missing_fields: list[str] = []
        if bridge_config is None or not bridge_config.bridge_is_enabled:
            missing_fields.append("bridge_is_enabled")
        if bridge_config is None or not bridge_config.bridge_base_url:
            missing_fields.append("bridge_base_url")
        if bridge_config is None or not bridge_config.bridge_api_key:
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
            base_url=bridge_config.bridge_base_url,
            api_key=bridge_config.bridge_api_key,
            timeout_seconds=self._settings.bridge_request_timeout_seconds,
        )


class CustomerBridgeService:
    def __init__(
        self,
        bridge_config_service: CustomerBridgeConfigService,
        bridge_client: BridgeClient,
        settings: Settings,
    ) -> None:
        self._bridge_config_service = bridge_config_service
        self._bridge_client = bridge_client
        self._config_resolver = CustomerBridgeConfigResolver(settings=settings)

    def get_health(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeHealthResult]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            bridge_health = self._bridge_client.get_health(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            if bridge_config is not None:
                bridge_config = self._bridge_config_service.persist_health_status(
                    bridge_config=bridge_config,
                    is_online=False,
                    checked_at=checked_at,
                    error=self._build_health_error_message(exc),
                )
            raise self._map_bridge_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_health_status(
                bridge_config=bridge_config,
                is_online=True,
                checked_at=checked_at,
                error=None,
            )
        return customer, bridge_config, bridge_health

    def refresh_status(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            self._bridge_client.get_health(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            if bridge_config is not None:
                bridge_config = self._bridge_config_service.persist_health_status(
                    bridge_config=bridge_config,
                    is_online=False,
                    checked_at=checked_at,
                    error=self._build_health_error_message(exc),
                )
            return customer, bridge_config
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_health_status(
                bridge_config=bridge_config,
                is_online=True,
                checked_at=checked_at,
                error=None,
            )
        return customer, bridge_config

    def get_capabilities(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeCapabilitiesResult]:
        customer, bridge_config, request = self._build_request(
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
            raise self._map_bridge_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        return customer, bridge_config, bridge_capabilities

    def _build_request(
        self,
        customer_id: int,
        correlation_id: str | None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeRequest]:
        customer, bridge_config = self._bridge_config_service.get(customer_id=customer_id)
        resolved_bridge_config = self._config_resolver.resolve(
            customer=customer,
            bridge_config=bridge_config,
        )
        return customer, bridge_config, BridgeRequest(
            base_url=resolved_bridge_config.base_url,
            api_key=resolved_bridge_config.api_key,
            timeout_seconds=resolved_bridge_config.timeout_seconds,
            correlation_id=correlation_id,
        )

    def _map_bridge_error(
        self,
        customer: Customer,
        bridge_base_url: str | None,
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
                        f"{bridge_base_url}: {exc}"
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

    def refresh_all_statuses(self) -> list[tuple[Customer, CustomerBridgeConfig | None]]:
        results: list[tuple[Customer, CustomerBridgeConfig | None]] = []
        for customer_id in self._bridge_config_service.list_refreshable_customer_ids():
            results.append(self.refresh_status(customer_id=customer_id))
        return results

    def _build_health_error_message(
        self,
        exc: (
            BridgeConnectionError
            | BridgeUnauthorizedError
            | BridgeUnexpectedStatusError
            | BridgeInvalidResponseError
        ),
    ) -> str:
        return str(exc)


def get_customer_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerService:
    return CustomerService(db_session=db_session)


def get_customer_bridge_config_service(
    db_session: Session = Depends(get_db_session),
    customer_service: CustomerService = Depends(get_customer_service),
) -> CustomerBridgeConfigService:
    return CustomerBridgeConfigService(
        db_session=db_session,
        customer_service=customer_service,
    )


def get_customer_bridge_service(
    customer_bridge_config_service: CustomerBridgeConfigService = Depends(get_customer_bridge_config_service),
    bridge_client: BridgeClient = Depends(get_bridge_client),
    settings: Settings = Depends(get_settings),
) -> CustomerBridgeService:
    return CustomerBridgeService(
        bridge_config_service=customer_bridge_config_service,
        bridge_client=bridge_client,
        settings=settings,
    )
