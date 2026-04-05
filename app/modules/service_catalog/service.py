from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.common.dtos import CurrentUser
from app.common.enums import SortOrder, UserRole
from app.common.formatters.jalali_datetime import gregorian_datetime_to_jalali_datetime_string
from app.common.messages import (
    CUSTOMER_ACCESS_DENIED,
    CUSTOMER_ID_INVALID_OR_INACTIVE,
    CUSTOMER_NOT_FOUND,
    CUSTOMER_SERVICE_CONFIG_IN_USE,
    CUSTOMER_SERVICE_CONFIG_NOT_FOUND,
    CUSTOMER_SERVICE_CONFIG_NOT_PURCHASABLE,
    CUSTOMER_SERVICE_CONFIG_SELECTION_INVALID,
    CUSTOMER_SERVICE_PURCHASE_NOT_FOUND,
    CUSTOMER_SERVICE_SELECTION_SNAPSHOT_NOT_FOUND,
    DATA_INTEGRITY_ERROR,
    DUPLICATE_CUSTOMER_SERVICE_PURCHASE_SELECTION,
    DUPLICATE_CUSTOMER_SERVICE_CONFIGURATION,
    DUPLICATE_SERVICE_ID_IN_PAYLOAD,
    GROUP_ID_CANNOT_BE_NULL,
    GROUP_ID_INVALID,
    INACTIVE_SERVICE_CANNOT_BE_ASSIGNED,
    PROJECT_ID_CANNOT_BE_NULL,
    PROJECT_ID_INVALID,
    SERVICE_GROUP_NOT_FOUND,
    SERVICE_ID_INVALID,
    SERVICE_NOT_FOUND,
    SERVICE_PROJECT_NOT_FOUND,
    SUPPORT_PRICE_CANNOT_BE_NULL,
    LOCAL_USER_CONTEXT_REQUIRED,
    USER_ID_INVALID,
)
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.service_catalog.dtos import (
    CustomerPricingSummaryCustomer,
    CustomerPricingSummaryGroup,
    CustomerPricingSummaryGroupTotals,
    CustomerPricingSummaryItem,
    CustomerPricingSummaryResult,
    CustomerPricingSummaryTotals,
    CustomerServiceConfigBulkUpsertCreate,
    CustomerServiceConfigCreate,
    CustomerServiceConfigUpdate,
    CustomerServicePurchaseCreate,
    CustomerServicePurchaseItemCreate,
    CustomerServiceSelectionSnapshotCreate,
    CustomerServiceTreeGroupOut,
    CustomerServiceTreeOut,
    CustomerServiceTreeProjectOut,
    CustomerServiceTreeServiceOut,
    CustomerServiceTreeTotalsOut,
    CustomerServicePurchaseUpdate,
    ServiceCreate,
    ServiceGroupCreate,
    ServiceGroupUpdate,
    ServiceProjectCreate,
    ServiceProjectUpdate,
    ServiceUpdate,
)
from app.modules.customers.dtos import CustomerOut
from app.modules.customers.schemas import Customer
from app.modules.service_catalog.schemas import (
    CustomerServiceConfig,
    CustomerServicePurchase,
    CustomerServicePurchaseItem,
    CustomerServiceSelectionSnapshot,
    Service,
    ServiceGroup,
    ServiceProject,
)
from app.modules.users.schemas import User


def get_current_snapshot_datetime() -> datetime:
    return datetime.now().replace(microsecond=0)


def _snapshot_day_start(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _snapshot_next_day_start(value: date) -> datetime:
    return datetime.combine(value + timedelta(days=1), time.min)


@dataclass
class ProjectHierarchyGroup:
    group: ServiceGroup
    services: list[Service]


@dataclass
class ProjectHierarchy:
    project: ServiceProject
    groups: list[ProjectHierarchyGroup]


@dataclass
class CustomerServiceSelectionSnapshotView:
    snapshot: CustomerServiceSelectionSnapshot
    customer_name: str
    user_name: str


class CustomerLookupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_or_404(self, customer_id: int) -> dict[str, int | str]:
        customer_table = Base.metadata.tables["customers"]
        customer_row = self._db_session.execute(
            select(
                customer_table.c.id,
                customer_table.c.name,
                customer_table.c.grade,
            ).where(customer_table.c.id == customer_id)
        ).mappings().first()
        if customer_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_NOT_FOUND,
            )
        return {
            "id": customer_row["id"],
            "name": customer_row["name"],
            "grade": customer_row["grade"],
        }

    def get_active_or_404(self, customer_id: int) -> dict[str, int | str]:
        customer_table = Base.metadata.tables["customers"]
        customer_row = self._db_session.execute(
            select(
                customer_table.c.id,
                customer_table.c.name,
                customer_table.c.grade,
            ).where(
                customer_table.c.id == customer_id,
                customer_table.c.is_active.is_(True),
            )
        ).mappings().first()
        if customer_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_NOT_FOUND,
            )
        return {
            "id": customer_row["id"],
            "name": customer_row["name"],
            "grade": customer_row["grade"],
        }


class UserLookupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_active_for_customer_snapshot_or_422(
        self,
        *,
        user_id: int,
        customer_id: int,
    ) -> User:
        user = self._db_session.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=USER_ID_INVALID,
            )
        if user.role == UserRole.CUSTOMER and user.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=USER_ID_INVALID,
            )
        return user


class ServiceProjectQueryBuilder:
    SORT_COLUMNS = {
        "id": ServiceProject.id,
        "name": ServiceProject.name,
        "sort_order": ServiceProject.sort_order,
        "is_active": ServiceProject.is_active,
        "created_at": ServiceProject.created_at,
        "updated_at": ServiceProject.updated_at,
    }

    def build_list_query(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[ServiceProject]]:
        query = select(ServiceProject)
        if is_active is None:
            query = query.where(ServiceProject.is_active.is_(True))
        else:
            query = query.where(ServiceProject.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    ServiceProject.name.ilike(search_pattern),
                    ServiceProject.description.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), ServiceProject.id.desc())
        else:
            query = query.order_by(sort_column.asc(), ServiceProject.id.asc())
        return query


class ServiceGroupQueryBuilder:
    SORT_COLUMNS = {
        "id": ServiceGroup.id,
        "name": ServiceGroup.name,
        "sort_order": ServiceGroup.sort_order,
        "is_active": ServiceGroup.is_active,
        "created_at": ServiceGroup.created_at,
        "updated_at": ServiceGroup.updated_at,
    }

    def build_list_query(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[ServiceGroup]]:
        query = select(ServiceGroup)
        if is_active is None:
            query = query.where(ServiceGroup.is_active.is_(True))
        else:
            query = query.where(ServiceGroup.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    ServiceGroup.name.ilike(search_pattern),
                    ServiceGroup.description.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(
                sort_column.desc(),
                ServiceGroup.sort_order.desc(),
                ServiceGroup.id.desc(),
            )
        else:
            query = query.order_by(
                sort_column.asc(),
                ServiceGroup.sort_order.asc(),
                ServiceGroup.id.asc(),
            )
        return query


class ServiceQueryBuilder:
    SORT_COLUMNS = {
        "id": Service.id,
        "project_id": Service.project_id,
        "group_id": Service.group_id,
        "project_sort_order": ServiceProject.sort_order,
        "group_sort_order": ServiceGroup.sort_order,
        "name": Service.name,
        "sort_order": Service.sort_order,
        "is_active": Service.is_active,
        "created_at": Service.created_at,
        "updated_at": Service.updated_at,
    }

    def build_list_query(
        self,
        project_id: int | None,
        group_id: int | None,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Service, ServiceGroup, ServiceProject]]:
        query = (
            select(Service, ServiceGroup, ServiceProject)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(
                ServiceGroup.is_active.is_(True),
                ServiceProject.is_active.is_(True),
            )
        )
        if project_id is not None:
            query = query.where(Service.project_id == project_id)
        if group_id is not None:
            query = query.where(Service.group_id == group_id)
        if is_active is None:
            query = query.where(Service.is_active.is_(True))
        else:
            query = query.where(Service.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Service.name.ilike(search_pattern),
                    Service.description.ilike(search_pattern),
                    ServiceGroup.name.ilike(search_pattern),
                    ServiceProject.name.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(
                sort_column.desc(),
                ServiceProject.sort_order.desc(),
                ServiceGroup.sort_order.desc(),
                Service.sort_order.desc(),
                Service.id.desc(),
            )
        else:
            query = query.order_by(
                sort_column.asc(),
                ServiceProject.sort_order.asc(),
                ServiceGroup.sort_order.asc(),
                Service.sort_order.asc(),
                Service.id.asc(),
            )
        return query


class ServiceProjectService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = ServiceProjectQueryBuilder()

    def create(self, dto: ServiceProjectCreate) -> ServiceProject:
        project = ServiceProject(
            name=dto.name,
            description=dto.description,
            sort_order=dto.sort_order,
            is_active=True,
        )
        self._db_session.add(project)
        self._commit_with_integrity_guard()
        self._db_session.refresh(project)
        return project

    def list(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[ServiceProject], PaginationMeta]:
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

    def list_all(self) -> list[ServiceProject]:
        query = self._query_builder.build_list_query(
            is_active=True,
            search=None,
            sort_by="sort_order",
            sort_order=SortOrder.ASC,
        )
        return list(self._db_session.scalars(query).all())

    def get_or_404(self, project_id: int) -> ServiceProject:
        project = self._db_session.get(ServiceProject, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_PROJECT_NOT_FOUND,
            )
        return project

    def get_active_or_404(self, project_id: int) -> ServiceProject:
        project = self.get_or_404(project_id=project_id)
        if not project.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_PROJECT_NOT_FOUND,
            )
        return project

    def update(self, project_id: int, dto: ServiceProjectUpdate) -> ServiceProject:
        project = self.get_or_404(project_id=project_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(project, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(project)
        return project

    def deactivate(self, project_id: int) -> ServiceProject:
        project = self.get_or_404(project_id=project_id)
        project.is_active = False
        self._db_session.commit()
        self._db_session.refresh(project)
        return project

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


class CustomerServiceConfigQueryBuilder:
    SORT_COLUMNS = {
        "id": CustomerServiceConfig.id,
        "project_id": Service.project_id,
        "project_name": ServiceProject.name,
        "project_sort_order": ServiceProject.sort_order,
        "service_id": Service.id,
        "service_name": Service.name,
        "group_name": ServiceGroup.name,
        "group_sort_order": ServiceGroup.sort_order,
        "service_sort_order": Service.sort_order,
        "is_enabled": CustomerServiceConfig.is_enabled,
        "sale_price": CustomerServiceConfig.sale_price,
        "support_price": CustomerServiceConfig.support_price,
        "created_at": CustomerServiceConfig.created_at,
        "updated_at": CustomerServiceConfig.updated_at,
    }

    def build_list_query(
        self,
        customer_id: int,
        project_id: int | None,
        is_enabled: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        *,
        only_active_relations: bool = False,
    ) -> Select[tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]]:
        query = (
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(CustomerServiceConfig.customer_id == customer_id)
        )
        if only_active_relations:
            query = query.where(
                Service.is_active.is_(True),
                ServiceGroup.is_active.is_(True),
                ServiceProject.is_active.is_(True),
            )
        if project_id is not None:
            query = query.where(Service.project_id == project_id)
        if is_enabled is not None:
            query = query.where(CustomerServiceConfig.is_enabled.is_(is_enabled))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Service.name.ilike(search_pattern),
                    ServiceGroup.name.ilike(search_pattern),
                    ServiceProject.name.ilike(search_pattern),
                    CustomerServiceConfig.notes.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(
                sort_column.desc(),
                ServiceProject.sort_order.desc(),
                ServiceGroup.sort_order.desc(),
                Service.sort_order.desc(),
                Service.id.desc(),
            )
        else:
            query = query.order_by(
                sort_column.asc(),
                ServiceProject.sort_order.asc(),
                ServiceGroup.sort_order.asc(),
                Service.sort_order.asc(),
                Service.id.asc(),
            )
        return query


class CustomerServiceConfigPolicy:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def validate_payload(self, items: list[CustomerServiceConfigCreate]) -> None:
        service_ids = [item.service_id for item in items]
        if len(service_ids) != len(set(service_ids)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=DUPLICATE_SERVICE_ID_IN_PAYLOAD,
            )

    def get_service_map(self, service_ids: list[int]) -> dict[int, Service]:
        services = list(
            self._db_session.scalars(
                select(Service).where(Service.id.in_(service_ids))
            ).all()
        )
        return {service.id: service for service in services}

    def get_existing_config_map(
        self,
        customer_id: int,
        service_ids: list[int],
    ) -> dict[int, CustomerServiceConfig]:
        existing_configs = list(
            self._db_session.scalars(
                select(CustomerServiceConfig).where(
                    CustomerServiceConfig.customer_id == customer_id,
                    CustomerServiceConfig.service_id.in_(service_ids),
                )
            ).all()
        )
        return {config.service_id: config for config in existing_configs}

    def validate_service_for_create(self, service: Service | None) -> None:
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=SERVICE_ID_INVALID,
            )
        if not service.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=INACTIVE_SERVICE_CANNOT_BE_ASSIGNED,
            )


class CustomerServiceConfigService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._customer_lookup_service = CustomerLookupService(db_session=db_session)
        self._access_policy = CustomerScopedAccessPolicy()
        self._policy = CustomerServiceConfigPolicy(db_session=db_session)
        self._query_builder = CustomerServiceConfigQueryBuilder()

    def list_by_customer(
        self,
        customer_id: int,
        project_id: int | None,
        is_enabled: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
        current_user: CurrentUser,
    ) -> tuple[list[tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]], PaginationMeta]:
        self._customer_lookup_service.get_active_or_404(customer_id=customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=customer_id,
        )
        query = self._query_builder.build_list_query(
            customer_id=customer_id,
            project_id=project_id,
            is_enabled=is_enabled,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            only_active_relations=True,
        )
        total_count = int(
            self._db_session.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            ) or 0
        )
        paginated_query = query.offset(pagination.offset).limit(pagination.page_size)
        rows = self._db_session.execute(paginated_query).all()
        items = [(row[0], row[1], row[2], row[3]) for row in rows]
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def bulk_upsert(
        self,
        customer_id: int,
        dto: CustomerServiceConfigBulkUpsertCreate,
    ) -> list[tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]]:
        self._customer_lookup_service.get_or_404(customer_id=customer_id)
        self._policy.validate_payload(items=dto.items)

        service_ids = [item.service_id for item in dto.items]
        service_map = self._policy.get_service_map(service_ids=service_ids)
        existing_config_map = self._policy.get_existing_config_map(
            customer_id=customer_id,
            service_ids=service_ids,
        )

        for item in dto.items:
            existing_config = existing_config_map.get(item.service_id)
            service = service_map.get(item.service_id)
            if existing_config is None:
                self._policy.validate_service_for_create(service=service)
                new_config = CustomerServiceConfig(
                    customer_id=customer_id,
                    service_id=item.service_id,
                    is_enabled=item.is_enabled,
                    sale_price=item.sale_price,
                    support_price=item.support_price,
                    notes=item.notes,
                )
                self._db_session.add(new_config)
                continue
            existing_config.is_enabled = item.is_enabled
            existing_config.sale_price = item.sale_price
            existing_config.support_price = item.support_price
            existing_config.notes = item.notes

        self._commit_with_integrity_guard()
        return self._list_joined_configs(customer_id=customer_id)

    def update_single(
        self,
        config_id: int,
        dto: CustomerServiceConfigUpdate,
    ) -> tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]:
        config = self._db_session.get(CustomerServiceConfig, config_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_SERVICE_CONFIG_NOT_FOUND,
            )
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        if "support_price" in update_data and update_data["support_price"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=SUPPORT_PRICE_CANNOT_BE_NULL,
            )
        for field_name, field_value in update_data.items():
            setattr(config, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(config)
        row = self._db_session.execute(
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(CustomerServiceConfig.id == config_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_SERVICE_CONFIG_NOT_FOUND,
            )
        return row[0], row[1], row[2], row[3]

    def delete_single(
        self,
        config_id: int,
    ) -> tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]:
        config, service, group, project = self._get_joined_config_or_404(config_id=config_id)
        self._db_session.delete(config)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=CUSTOMER_SERVICE_CONFIG_IN_USE,
            ) from exc
        return config, service, group, project

    def _list_joined_configs(
        self,
        customer_id: int,
    ) -> list[tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]]:
        rows = self._db_session.execute(
            self._query_builder.build_list_query(
                customer_id=customer_id,
                project_id=None,
                is_enabled=None,
                search=None,
                sort_by="project_sort_order",
                sort_order=SortOrder.ASC,
            )
        ).all()
        return [(row[0], row[1], row[2], row[3]) for row in rows]

    def _get_joined_config_or_404(
        self,
        *,
        config_id: int,
    ) -> tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]:
        row = self._db_session.execute(
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(CustomerServiceConfig.id == config_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_SERVICE_CONFIG_NOT_FOUND,
            )
        return row[0], row[1], row[2], row[3]

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            error_text = str(exc.orig).lower()
            if "customer_service_configs" in error_text or "service_id" in error_text:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=DUPLICATE_CUSTOMER_SERVICE_CONFIGURATION,
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


@dataclass(frozen=True)
class CustomerServicePurchaseDetails:
    purchase: CustomerServicePurchase
    items: list[CustomerServicePurchaseItem]


@dataclass(frozen=True)
class CustomerServicePurchaseTotals:
    sale_total: int
    support_total: int
    grand_total: int


@dataclass(frozen=True)
class ResolvedCustomerServicePurchaseSelection:
    config: CustomerServiceConfig
    service: Service
    group: ServiceGroup
    project: ServiceProject


class CustomerScopedAccessPolicy:
    def validate_customer_access(
        self,
        *,
        current_user: CurrentUser,
        customer_id: int,
    ) -> None:
        role_label = current_user.role.value if current_user.role is not None else "unknown"
        if current_user.role == UserRole.ADMIN:
            return
        has_customer_access = (
            current_user.role == UserRole.CUSTOMER
            and current_user.customer_id == customer_id
        )
        if has_customer_access:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": CUSTOMER_ACCESS_DENIED,
                "developer_message": (
                    f"User {current_user.user_id} with role {role_label} "
                    f"cannot access customer {customer_id}."
                ),
            },
        )


class CustomerServicePurchaseQueryBuilder:
    SORT_COLUMNS = {
        "id": CustomerServicePurchase.id,
        "selected_count": CustomerServicePurchase.selected_count,
        "sale_total": CustomerServicePurchase.sale_total,
        "support_total": CustomerServicePurchase.support_total,
        "grand_total": CustomerServicePurchase.grand_total,
        "is_active": CustomerServicePurchase.is_active,
        "created_at": CustomerServicePurchase.created_at,
        "updated_at": CustomerServicePurchase.updated_at,
    }

    def build_list_query(
        self,
        *,
        customer_id: int,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[CustomerServicePurchase]]:
        query = select(CustomerServicePurchase).where(
            CustomerServicePurchase.customer_id == customer_id
        )
        if is_active is None:
            query = query.where(CustomerServicePurchase.is_active.is_(True))
        else:
            query = query.where(CustomerServicePurchase.is_active.is_(is_active))
        if search:
            query = query.where(CustomerServicePurchase.notes.ilike(f"%{search}%"))
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(
                sort_column.desc(),
                CustomerServicePurchase.id.desc(),
            )
        else:
            query = query.order_by(
                sort_column.asc(),
                CustomerServicePurchase.id.asc(),
            )
        return query


class CustomerServiceSelectionSnapshotQueryBuilder:
    SORT_COLUMNS = {
        "id": CustomerServiceSelectionSnapshot.id,
        "user_id": CustomerServiceSelectionSnapshot.user_id,
        "date": CustomerServiceSelectionSnapshot.selected_at,
    }

    def build_list_query(
        self,
        *,
        customer_id: int,
        user_id: int | None,
        from_date: date | None,
        to_date: date | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[CustomerServiceSelectionSnapshot, str, str]]:
        query = (
            select(
                CustomerServiceSelectionSnapshot,
                Customer.name,
                User.full_name,
            )
            .join(Customer, Customer.id == CustomerServiceSelectionSnapshot.customer_id)
            .join(User, User.id == CustomerServiceSelectionSnapshot.user_id)
            .where(CustomerServiceSelectionSnapshot.customer_id == customer_id)
        )
        if user_id is not None:
            query = query.where(CustomerServiceSelectionSnapshot.user_id == user_id)
        if from_date is not None:
            query = query.where(CustomerServiceSelectionSnapshot.selected_at >= _snapshot_day_start(from_date))
        if to_date is not None:
            query = query.where(CustomerServiceSelectionSnapshot.selected_at < _snapshot_next_day_start(to_date))
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(
                sort_column.desc(),
                CustomerServiceSelectionSnapshot.id.desc(),
            )
        else:
            query = query.order_by(
                sort_column.asc(),
                CustomerServiceSelectionSnapshot.id.asc(),
            )
        return query


class CustomerServicePurchaseSelectionPolicy:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def validate_payload(
        self,
        items: list[CustomerServicePurchaseItemCreate],
    ) -> None:
        config_ids = [item.customer_service_config_id for item in items]
        if len(config_ids) != len(set(config_ids)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=DUPLICATE_CUSTOMER_SERVICE_PURCHASE_SELECTION,
            )

    def resolve_items(
        self,
        *,
        customer_id: int,
        items: list[CustomerServicePurchaseItemCreate],
    ) -> list[ResolvedCustomerServicePurchaseSelection]:
        self.validate_payload(items=items)
        config_ids = [item.customer_service_config_id for item in items]
        rows = self._db_session.execute(
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(
                CustomerServiceConfig.customer_id == customer_id,
                CustomerServiceConfig.id.in_(config_ids),
            )
        ).all()
        selection_map = {
            row[0].id: ResolvedCustomerServicePurchaseSelection(
                config=row[0],
                service=row[1],
                group=row[2],
                project=row[3],
            )
            for row in rows
        }
        selections: list[ResolvedCustomerServicePurchaseSelection] = []
        for item in items:
            selection = selection_map.get(item.customer_service_config_id)
            if selection is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=CUSTOMER_SERVICE_CONFIG_SELECTION_INVALID,
                )
            is_purchasable = (
                selection.config.is_enabled
                and selection.service.is_active
                and selection.group.is_active
                and selection.project.is_active
            )
            if not is_purchasable:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=CUSTOMER_SERVICE_CONFIG_NOT_PURCHASABLE,
                )
            selections.append(selection)
        return selections


class CustomerServicePurchaseService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._customer_lookup_service = CustomerLookupService(db_session=db_session)
        self._access_policy = CustomerScopedAccessPolicy()
        self._query_builder = CustomerServicePurchaseQueryBuilder()
        self._selection_policy = CustomerServicePurchaseSelectionPolicy(
            db_session=db_session,
        )

    def list_by_customer(
        self,
        *,
        customer_id: int,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
        current_user: CurrentUser,
    ) -> tuple[list[CustomerServicePurchaseDetails], PaginationMeta]:
        self._customer_lookup_service.get_active_or_404(customer_id=customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=customer_id,
        )
        query = self._query_builder.build_list_query(
            customer_id=customer_id,
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
        purchases = list(self._db_session.scalars(paginated_query).all())
        items_by_purchase_id = self._get_items_by_purchase_ids(
            purchase_ids=[purchase.id for purchase in purchases]
        )
        details = [
            CustomerServicePurchaseDetails(
                purchase=purchase,
                items=items_by_purchase_id.get(purchase.id, []),
            )
            for purchase in purchases
        ]
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return details, meta

    def create(
        self,
        *,
        customer_id: int,
        dto: CustomerServicePurchaseCreate,
        current_user: CurrentUser,
    ) -> CustomerServicePurchaseDetails:
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=LOCAL_USER_CONTEXT_REQUIRED,
            )
        self._customer_lookup_service.get_active_or_404(customer_id=customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=customer_id,
        )
        purchase = CustomerServicePurchase(
            customer_id=customer_id,
            created_by_user_id=current_user.id,
            notes=dto.notes,
            sale_total=0,
            support_total=0,
            grand_total=0,
            selected_count=0,
            is_active=True,
        )
        self._db_session.add(purchase)
        self._db_session.flush()
        self._replace_purchase_items(
            purchase=purchase,
            item_payloads=dto.items,
        )
        self._commit_with_integrity_guard()
        self._db_session.refresh(purchase)
        return self.get_by_id(
            purchase_id=purchase.id,
            current_user=current_user,
            include_inactive=True,
        )

    def get_by_id(
        self,
        *,
        purchase_id: int,
        current_user: CurrentUser,
        include_inactive: bool = False,
    ) -> CustomerServicePurchaseDetails:
        purchase = self._get_purchase_or_404(
            purchase_id=purchase_id,
            include_inactive=include_inactive,
        )
        self._customer_lookup_service.get_active_or_404(customer_id=purchase.customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=purchase.customer_id,
        )
        return CustomerServicePurchaseDetails(
            purchase=purchase,
            items=self._get_items_for_purchase(purchase_id=purchase.id),
        )

    def update(
        self,
        *,
        purchase_id: int,
        dto: CustomerServicePurchaseUpdate,
        current_user: CurrentUser,
    ) -> CustomerServicePurchaseDetails:
        purchase = self._get_purchase_or_404(
            purchase_id=purchase_id,
            include_inactive=False,
        )
        self._customer_lookup_service.get_active_or_404(customer_id=purchase.customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=purchase.customer_id,
        )
        if "notes" in dto.model_fields_set:
            purchase.notes = dto.notes
        if "items" in dto.model_fields_set and dto.items is not None:
            self._replace_purchase_items(
                purchase=purchase,
                item_payloads=dto.items,
            )
        self._commit_with_integrity_guard()
        self._db_session.refresh(purchase)
        return self.get_by_id(
            purchase_id=purchase.id,
            current_user=current_user,
            include_inactive=True,
        )

    def deactivate(
        self,
        *,
        purchase_id: int,
        current_user: CurrentUser,
    ) -> CustomerServicePurchaseDetails:
        purchase = self._get_purchase_or_404(
            purchase_id=purchase_id,
            include_inactive=False,
        )
        self._customer_lookup_service.get_active_or_404(customer_id=purchase.customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=purchase.customer_id,
        )
        purchase.is_active = False
        self._commit_with_integrity_guard()
        self._db_session.refresh(purchase)
        return self.get_by_id(
            purchase_id=purchase.id,
            current_user=current_user,
            include_inactive=True,
        )

    def _get_purchase_or_404(
        self,
        *,
        purchase_id: int,
        include_inactive: bool,
    ) -> CustomerServicePurchase:
        purchase = self._db_session.get(CustomerServicePurchase, purchase_id)
        if purchase is None or (not include_inactive and not purchase.is_active):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_SERVICE_PURCHASE_NOT_FOUND,
            )
        return purchase

    def _replace_purchase_items(
        self,
        *,
        purchase: CustomerServicePurchase,
        item_payloads: list[CustomerServicePurchaseItemCreate],
    ) -> None:
        selections = self._selection_policy.resolve_items(
            customer_id=purchase.customer_id,
            items=item_payloads,
        )
        totals = self._calculate_totals(selections=selections)
        purchase.selected_count = len(selections)
        purchase.sale_total = totals.sale_total
        purchase.support_total = totals.support_total
        purchase.grand_total = totals.grand_total
        self._db_session.execute(
            delete(CustomerServicePurchaseItem).where(
                CustomerServicePurchaseItem.customer_service_purchase_id == purchase.id
            )
        )
        for selection in selections:
            self._db_session.add(
                CustomerServicePurchaseItem(
                    customer_service_purchase_id=purchase.id,
                    customer_service_config_id=selection.config.id,
                    service_id=selection.service.id,
                    project_id=selection.project.id,
                    project_name=selection.project.name,
                    group_id=selection.group.id,
                    group_name=selection.group.name,
                    service_name=selection.service.name,
                    sale_price=selection.config.sale_price,
                    support_price=selection.config.support_price,
                )
            )

    def _calculate_totals(
        self,
        *,
        selections: list[ResolvedCustomerServicePurchaseSelection],
    ) -> CustomerServicePurchaseTotals:
        sale_total = 0
        support_total = 0
        for selection in selections:
            sale_total += selection.config.sale_price or 0
            support_total += selection.config.support_price
        return CustomerServicePurchaseTotals(
            sale_total=sale_total,
            support_total=support_total,
            grand_total=sale_total + support_total,
        )

    def _get_items_by_purchase_ids(
        self,
        *,
        purchase_ids: list[int],
    ) -> dict[int, list[CustomerServicePurchaseItem]]:
        if not purchase_ids:
            return {}
        items = list(
            self._db_session.scalars(
                select(CustomerServicePurchaseItem)
                .where(
                    CustomerServicePurchaseItem.customer_service_purchase_id.in_(
                        purchase_ids
                    )
                )
                .order_by(
                    CustomerServicePurchaseItem.customer_service_purchase_id.asc(),
                    CustomerServicePurchaseItem.id.asc(),
                )
            ).all()
        )
        items_by_purchase_id: dict[int, list[CustomerServicePurchaseItem]] = {}
        for item in items:
            items_by_purchase_id.setdefault(
                item.customer_service_purchase_id,
                [],
            ).append(item)
        return items_by_purchase_id

    def _get_items_for_purchase(
        self,
        *,
        purchase_id: int,
    ) -> list[CustomerServicePurchaseItem]:
        return list(
            self._db_session.scalars(
                select(CustomerServicePurchaseItem)
                .where(CustomerServicePurchaseItem.customer_service_purchase_id == purchase_id)
                .order_by(CustomerServicePurchaseItem.id.asc())
            ).all()
        )

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            error_text = str(exc.orig).lower()
            if (
                "customer_service_purchase_items" in error_text
                and "customer_service_config_id" in error_text
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=DUPLICATE_CUSTOMER_SERVICE_PURCHASE_SELECTION,
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


class CustomerServiceSelectionSnapshotService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._customer_lookup_service = CustomerLookupService(db_session=db_session)
        self._user_lookup_service = UserLookupService(db_session=db_session)
        self._access_policy = CustomerScopedAccessPolicy()
        self._query_builder = CustomerServiceSelectionSnapshotQueryBuilder()

    def list_by_customer(
        self,
        *,
        customer_id: int,
        user_id: int | None,
        from_date: date | None,
        to_date: date | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
        current_user: CurrentUser,
    ) -> tuple[list[CustomerServiceSelectionSnapshotView], PaginationMeta]:
        self._customer_lookup_service.get_active_or_404(customer_id=customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=customer_id,
        )
        if user_id is not None:
            self._user_lookup_service.get_active_for_customer_snapshot_or_422(
                user_id=user_id,
                customer_id=customer_id,
            )
        query = self._query_builder.build_list_query(
            customer_id=customer_id,
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total_count = int(
            self._db_session.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            ) or 0
        )
        paginated_query = query.offset(pagination.offset).limit(pagination.page_size)
        rows = self._db_session.execute(paginated_query).all()
        items = [
            CustomerServiceSelectionSnapshotView(
                snapshot=row[0],
                customer_name=row[1],
                user_name=row[2],
            )
            for row in rows
        ]
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def create(
        self,
        *,
        path_customer_id: int,
        dto: CustomerServiceSelectionSnapshotCreate,
        current_user: CurrentUser,
    ) -> CustomerServiceSelectionSnapshot:
        if dto.customer_id != path_customer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=CUSTOMER_ID_INVALID_OR_INACTIVE,
            )
        self._customer_lookup_service.get_active_or_404(customer_id=dto.customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=dto.customer_id,
        )
        target_user = self._user_lookup_service.get_active_for_customer_snapshot_or_422(
            user_id=dto.user_id,
            customer_id=dto.customer_id,
        )
        if current_user.role != UserRole.ADMIN and target_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=USER_ID_INVALID,
            )
        snapshot_timestamp = get_current_snapshot_datetime()
        snapshot = CustomerServiceSelectionSnapshot(
            customer_id=dto.customer_id,
            user_id=target_user.id,
            selected_at=snapshot_timestamp,
            created_at=snapshot_timestamp,
            updated_at=snapshot_timestamp,
            payload=dto.payload,
        )
        self._db_session.add(snapshot)
        self._commit_with_integrity_guard()
        self._db_session.refresh(snapshot)
        return snapshot

    def get_by_id(
        self,
        *,
        snapshot_id: int,
        current_user: CurrentUser,
    ) -> CustomerServiceSelectionSnapshotView:
        snapshot = self._get_snapshot_view_or_404(snapshot_id=snapshot_id)
        self._customer_lookup_service.get_active_or_404(customer_id=snapshot.snapshot.customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=snapshot.snapshot.customer_id,
        )
        return snapshot

    def _get_snapshot_view_or_404(
        self,
        *,
        snapshot_id: int,
    ) -> CustomerServiceSelectionSnapshotView:
        row = self._db_session.execute(
            select(
                CustomerServiceSelectionSnapshot,
                Customer.name,
                User.full_name,
            )
            .join(Customer, Customer.id == CustomerServiceSelectionSnapshot.customer_id)
            .join(User, User.id == CustomerServiceSelectionSnapshot.user_id)
            .where(CustomerServiceSelectionSnapshot.id == snapshot_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_SERVICE_SELECTION_SNAPSHOT_NOT_FOUND,
            )
        return CustomerServiceSelectionSnapshotView(
            snapshot=row[0],
            customer_name=row[1],
            user_name=row[2],
        )

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


class CustomerServiceTreeService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._access_policy = CustomerScopedAccessPolicy()

    def get_tree(
        self,
        *,
        customer_id: int,
        current_user: CurrentUser,
    ) -> CustomerServiceTreeOut:
        customer = self._get_active_customer_or_404(customer_id=customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=customer_id,
        )
        rows = self._db_session.execute(
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(
                CustomerServiceConfig.customer_id == customer_id,
                Service.is_active.is_(True),
                ServiceGroup.is_active.is_(True),
                ServiceProject.is_active.is_(True),
            )
            .order_by(
                ServiceProject.sort_order.asc(),
                ServiceProject.id.asc(),
                ServiceGroup.sort_order.asc(),
                ServiceGroup.id.asc(),
                Service.sort_order.asc(),
                Service.id.asc(),
                CustomerServiceConfig.id.asc(),
            )
        ).all()

        project_nodes: list[CustomerServiceTreeProjectOut] = []
        project_bucket: dict[int, CustomerServiceTreeProjectOut] = {}
        group_bucket: dict[tuple[int, int], CustomerServiceTreeGroupOut] = {}
        overall_totals = self._new_totals()

        for row in rows:
            config: CustomerServiceConfig = row[0]
            service: Service = row[1]
            group: ServiceGroup = row[2]
            project: ServiceProject = row[3]

            project_node = project_bucket.get(project.id)
            if project_node is None:
                project_node = CustomerServiceTreeProjectOut(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    sort_order=project.sort_order,
                    is_active=project.is_active,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    totals=self._new_totals(),
                    groups=[],
                )
                project_bucket[project.id] = project_node
                project_nodes.append(project_node)

            group_key = (project.id, group.id)
            group_node = group_bucket.get(group_key)
            if group_node is None:
                group_node = CustomerServiceTreeGroupOut(
                    id=group.id,
                    name=group.name,
                    description=group.description,
                    sort_order=group.sort_order,
                    is_active=group.is_active,
                    created_at=group.created_at,
                    updated_at=group.updated_at,
                    totals=self._new_totals(),
                    services=[],
                )
                group_bucket[group_key] = group_node
                project_node.groups.append(group_node)

            sale_price_value = config.sale_price if config.sale_price is not None else 0
            line_sale_total = sale_price_value if config.is_enabled else 0
            line_support_total = config.support_price if config.is_enabled else 0
            line_grand_total = line_sale_total + line_support_total

            group_node.services.append(
                CustomerServiceTreeServiceOut(
                    config_id=config.id,
                    customer_id=config.customer_id,
                    service_id=service.id,
                    service_name=service.name,
                    service_description=service.description,
                    service_sort_order=service.sort_order,
                    service_is_active=service.is_active,
                    is_enabled=config.is_enabled,
                    sale_price=config.sale_price,
                    support_price=config.support_price,
                    notes=config.notes,
                    line_sale_total=line_sale_total,
                    line_support_total=line_support_total,
                    line_grand_total=line_grand_total,
                    config_created_at=config.created_at,
                    config_updated_at=config.updated_at,
                    service_created_at=service.created_at,
                    service_updated_at=service.updated_at,
                )
            )

            self._accumulate_totals(
                totals=group_node.totals,
                is_enabled=config.is_enabled,
                line_sale_total=line_sale_total,
                line_support_total=line_support_total,
                line_grand_total=line_grand_total,
            )
            self._accumulate_totals(
                totals=project_node.totals,
                is_enabled=config.is_enabled,
                line_sale_total=line_sale_total,
                line_support_total=line_support_total,
                line_grand_total=line_grand_total,
            )
            self._accumulate_totals(
                totals=overall_totals,
                is_enabled=config.is_enabled,
                line_sale_total=line_sale_total,
                line_support_total=line_support_total,
                line_grand_total=line_grand_total,
            )

        return CustomerServiceTreeOut(
            customer=CustomerOut(
                id=customer.id,
                name=customer.name,
                manager_name=customer.manager_name,
                grade=customer.grade,
                is_active=customer.is_active,
                created_at=customer.created_at,
                updated_at=gregorian_datetime_to_jalali_datetime_string(customer.updated_at),
            ),
            projects=project_nodes,
            totals=overall_totals,
        )

    def _get_active_customer_or_404(self, *, customer_id: int) -> Customer:
        customer = self._db_session.get(Customer, customer_id)
        if customer is None or not customer.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_NOT_FOUND,
            )
        return customer

    def _new_totals(self) -> CustomerServiceTreeTotalsOut:
        return CustomerServiceTreeTotalsOut(
            configured_service_count=0,
            enabled_service_count=0,
            sale_total=0,
            support_total=0,
            grand_total=0,
        )

    def _accumulate_totals(
        self,
        *,
        totals: CustomerServiceTreeTotalsOut,
        is_enabled: bool,
        line_sale_total: int,
        line_support_total: int,
        line_grand_total: int,
    ) -> None:
        totals.configured_service_count += 1
        if is_enabled:
            totals.enabled_service_count += 1
        totals.sale_total += line_sale_total
        totals.support_total += line_support_total
        totals.grand_total += line_grand_total


class CustomerPricingSummaryService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._customer_lookup_service = CustomerLookupService(db_session=db_session)

    def get_summary(self, customer_id: int) -> CustomerPricingSummaryResult:
        customer = self._customer_lookup_service.get_active_or_404(customer_id=customer_id)
        rows = self._db_session.execute(
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(
                CustomerServiceConfig.customer_id == customer_id,
                Service.is_active.is_(True),
                ServiceGroup.is_active.is_(True),
                ServiceProject.is_active.is_(True),
            )
            .order_by(
                ServiceProject.sort_order.asc(),
                ServiceGroup.sort_order.asc(),
                Service.sort_order.asc(),
                Service.id.asc(),
            )
        ).all()

        group_bucket: dict[tuple[int, int], CustomerPricingSummaryGroup] = {}
        total_sale = 0
        total_support = 0

        for row in rows:
            config: CustomerServiceConfig = row[0]
            service: Service = row[1]
            group: ServiceGroup = row[2]
            project: ServiceProject = row[3]

            sale_price_value = config.sale_price if config.sale_price is not None else 0
            support_price_value = config.support_price
            line_sale_total = sale_price_value if config.is_enabled else 0
            line_support_total = support_price_value if config.is_enabled else 0
            line_grand_total = line_sale_total + line_support_total

            bucket_key = (project.id, group.id)
            group_entry = group_bucket.get(bucket_key)
            if group_entry is None:
                group_entry = CustomerPricingSummaryGroup(
                    project_id=project.id,
                    project_name=project.name,
                    group_id=group.id,
                    group_name=group.name,
                    items=[],
                    totals=CustomerPricingSummaryGroupTotals(
                        sale_total=0,
                        support_total=0,
                        grand_total=0,
                    ),
                )
                group_bucket[bucket_key] = group_entry

            group_entry.items.append(
                CustomerPricingSummaryItem(
                    service_id=service.id,
                    service_name=service.name,
                    is_enabled=config.is_enabled,
                    sale_price=config.sale_price,
                    support_price=config.support_price,
                    line_sale_total=line_sale_total,
                    line_support_total=line_support_total,
                    line_grand_total=line_grand_total,
                )
            )

            if config.is_enabled:
                group_entry.totals.sale_total += line_sale_total
                group_entry.totals.support_total += line_support_total
                group_entry.totals.grand_total += line_grand_total
                total_sale += line_sale_total
                total_support += line_support_total

        groups = list(group_bucket.values())
        return CustomerPricingSummaryResult(
            customer=CustomerPricingSummaryCustomer(
                id=int(customer["id"]),
                name=str(customer["name"]),
                grade=int(customer["grade"]),
            ),
            groups=groups,
            totals=CustomerPricingSummaryTotals(
                sale_total=total_sale,
                support_total=total_support,
                grand_total=total_sale + total_support,
            ),
        )


def get_service_project_service(
    db_session: Session = Depends(get_db_session),
) -> ServiceProjectService:
    return ServiceProjectService(db_session=db_session)


def get_service_group_service(
    db_session: Session = Depends(get_db_session),
) -> ServiceGroupService:
    return ServiceGroupService(db_session=db_session)


def get_service_catalog_service(
    db_session: Session = Depends(get_db_session),
) -> ServiceCatalogService:
    return ServiceCatalogService(db_session=db_session)


def get_customer_service_config_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerServiceConfigService:
    return CustomerServiceConfigService(db_session=db_session)


def get_customer_service_purchase_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerServicePurchaseService:
    return CustomerServicePurchaseService(db_session=db_session)


def get_customer_service_selection_snapshot_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerServiceSelectionSnapshotService:
    return CustomerServiceSelectionSnapshotService(db_session=db_session)


def get_customer_service_tree_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerServiceTreeService:
    return CustomerServiceTreeService(db_session=db_session)


def get_customer_pricing_summary_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerPricingSummaryService:
    return CustomerPricingSummaryService(db_session=db_session)


class ServiceGroupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = ServiceGroupQueryBuilder()

    def create(self, dto: ServiceGroupCreate) -> ServiceGroup:
        group = ServiceGroup(
            name=dto.name,
            description=dto.description,
            sort_order=dto.sort_order,
            is_active=True,
        )
        self._db_session.add(group)
        self._commit_with_integrity_guard()
        self._db_session.refresh(group)
        return group

    def list(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[ServiceGroup], PaginationMeta]:
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

    def list_all(self) -> list[ServiceGroup]:
        query = self._query_builder.build_list_query(
            is_active=True,
            search=None,
            sort_by="sort_order",
            sort_order=SortOrder.ASC,
        )
        return list(self._db_session.scalars(query).all())

    def get_or_404(self, group_id: int) -> ServiceGroup:
        group = self._db_session.get(ServiceGroup, group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_GROUP_NOT_FOUND,
            )
        return group

    def get_active_or_404(self, group_id: int) -> ServiceGroup:
        group = self.get_or_404(group_id=group_id)
        if not group.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_GROUP_NOT_FOUND,
            )
        return group

    def update(self, group_id: int, dto: ServiceGroupUpdate) -> ServiceGroup:
        group = self.get_or_404(group_id=group_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(group, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(group)
        return group

    def deactivate(self, group_id: int) -> ServiceGroup:
        group = self.get_or_404(group_id=group_id)
        group.is_active = False
        self._db_session.commit()
        self._db_session.refresh(group)
        return group

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc


class ServiceCatalogService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = ServiceQueryBuilder()

    def create(self, dto: ServiceCreate) -> tuple[Service, ServiceGroup, ServiceProject]:
        project = self._get_project_or_422(project_id=dto.project_id)
        group = self._get_group_or_422(group_id=dto.group_id)
        service = Service(
            project_id=project.id,
            group_id=group.id,
            name=dto.name,
            description=dto.description,
            is_active=True,
            sort_order=dto.sort_order,
        )
        self._db_session.add(service)
        self._commit_with_integrity_guard()
        self._db_session.refresh(service)
        return service, group, project

    def list(
        self,
        project_id: int | None,
        group_id: int | None,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[tuple[Service, ServiceGroup, ServiceProject]], PaginationMeta]:
        query = self._query_builder.build_list_query(
            project_id=project_id,
            group_id=group_id,
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
        rows = self._db_session.execute(paginated_query).all()
        items = [(row[0], row[1], row[2]) for row in rows]
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def list_grouped_by_project(self, project_id: int | None) -> list[ProjectHierarchy]:
        if project_id is None:
            projects = list(
                self._db_session.scalars(
                    select(ServiceProject)
                    .where(ServiceProject.is_active.is_(True))
                    .order_by(ServiceProject.sort_order.asc(), ServiceProject.id.asc())
                ).all()
            )
        else:
            project = self._get_project_or_404(project_id=project_id)
            if not project.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=SERVICE_PROJECT_NOT_FOUND,
                )
            projects = [project]

        if not projects:
            return []

        project_ids = [project.id for project in projects]
        project_bucket = {
            project.id: ProjectHierarchy(project=project, groups=[])
            for project in projects
        }

        rows = self._db_session.execute(
            select(Service, ServiceGroup, ServiceProject)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(
                Service.project_id.in_(project_ids),
                Service.is_active.is_(True),
                ServiceGroup.is_active.is_(True),
                ServiceProject.is_active.is_(True),
            )
            .order_by(
                ServiceProject.sort_order.asc(),
                ServiceProject.id.asc(),
                ServiceGroup.sort_order.asc(),
                ServiceGroup.id.asc(),
                Service.sort_order.asc(),
                Service.id.asc(),
            )
        ).all()

        group_bucket: dict[tuple[int, int], ProjectHierarchyGroup] = {}
        for row in rows:
            service: Service = row[0]
            group: ServiceGroup = row[1]
            project: ServiceProject = row[2]
            bucket_key = (project.id, group.id)
            group_entry = group_bucket.get(bucket_key)
            if group_entry is None:
                group_entry = ProjectHierarchyGroup(group=group, services=[])
                group_bucket[bucket_key] = group_entry
                project_bucket[project.id].groups.append(group_entry)
            group_entry.services.append(service)

        return list(project_bucket.values())

    def get_or_404(self, service_id: int) -> tuple[Service, ServiceGroup, ServiceProject]:
        row = self._db_session.execute(
            select(Service, ServiceGroup, ServiceProject)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(Service.id == service_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_NOT_FOUND,
            )
        return row[0], row[1], row[2]

    def get_active_or_404(self, service_id: int) -> tuple[Service, ServiceGroup, ServiceProject]:
        row = self._db_session.execute(
            select(Service, ServiceGroup, ServiceProject)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == Service.project_id)
            .where(
                Service.id == service_id,
                Service.is_active.is_(True),
                ServiceGroup.is_active.is_(True),
                ServiceProject.is_active.is_(True),
            )
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_NOT_FOUND,
            )
        return row[0], row[1], row[2]

    def update(self, service_id: int, dto: ServiceUpdate) -> tuple[Service, ServiceGroup, ServiceProject]:
        service, _, _ = self.get_or_404(service_id=service_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)

        if "project_id" in update_data:
            project_id = update_data["project_id"]
            if project_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=PROJECT_ID_CANNOT_BE_NULL,
                )
            self._get_project_or_422(project_id=project_id)

        if "group_id" in update_data:
            group_id = update_data["group_id"]
            if group_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=GROUP_ID_CANNOT_BE_NULL,
                )
            self._get_group_or_422(group_id=group_id)

        for field_name, field_value in update_data.items():
            setattr(service, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(service)
        return self.get_or_404(service_id=service_id)

    def deactivate(self, service_id: int) -> tuple[Service, ServiceGroup, ServiceProject]:
        service, _, _ = self.get_or_404(service_id=service_id)
        service.is_active = False
        self._db_session.commit()
        self._db_session.refresh(service)
        return self.get_or_404(service_id=service_id)

    def _get_group_or_422(self, group_id: int) -> ServiceGroup:
        group = self._db_session.get(ServiceGroup, group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=GROUP_ID_INVALID,
            )
        return group

    def _get_project_or_404(self, project_id: int) -> ServiceProject:
        project = self._db_session.get(ServiceProject, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_PROJECT_NOT_FOUND,
            )
        return project

    def _get_project_or_422(self, project_id: int) -> ServiceProject:
        project = self._db_session.get(ServiceProject, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=PROJECT_ID_INVALID,
            )
        return project

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
