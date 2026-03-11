from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.common.enums import SortOrder
from app.common.messages import (
    DATA_INTEGRITY_ERROR,
    DUPLICATE_CUSTOMER_SERVICE_CONFIGURATION,
    DUPLICATE_SERVICE_ID_IN_PAYLOAD,
    GROUP_ID_CANNOT_BE_NULL,
    GROUP_ID_INVALID,
    INACTIVE_SERVICE_CANNOT_BE_ASSIGNED,
    CUSTOMER_NOT_FOUND,
    CUSTOMER_SERVICE_CONFIG_NOT_FOUND,
    PROJECT_ID_CANNOT_BE_NULL,
    PROJECT_ID_INVALID,
    SALE_PRICE_CANNOT_BE_NULL,
    SERVICE_GROUP_NOT_FOUND,
    SERVICE_ID_INVALID,
    SERVICE_NOT_FOUND,
    SERVICE_PROJECT_NOT_FOUND,
)
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.service_catalog.dtos import (
    CustomerPricingSummaryGroup,
    CustomerPricingSummaryGroupTotals,
    CustomerPricingSummaryItem,
    CustomerPricingSummaryCustomer,
    CustomerPricingSummaryResult,
    CustomerPricingSummaryTotals,
    CustomerServiceConfigBulkUpsertCreate,
    CustomerServiceConfigCreate,
    CustomerServiceConfigUpdate,
    ServiceCreate,
    ServiceGroupCreate,
    ServiceGroupUpdate,
    ServiceProjectCreate,
    ServiceProjectUpdate,
    ServiceUpdate,
)
from app.modules.service_catalog.schemas import CustomerServiceConfig, Service, ServiceGroup, ServiceProject


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
        if is_active is not None:
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
        "project_id": ServiceGroup.project_id,
        "project_sort_order": ServiceProject.sort_order,
        "code": ServiceGroup.code,
        "name": ServiceGroup.name,
        "sort_order": ServiceGroup.sort_order,
        "is_active": ServiceGroup.is_active,
        "created_at": ServiceGroup.created_at,
        "updated_at": ServiceGroup.updated_at,
    }

    def build_list_query(
        self,
        project_id: int | None,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[ServiceGroup, ServiceProject]]:
        query = select(ServiceGroup, ServiceProject).join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
        if project_id is not None:
            query = query.where(ServiceGroup.project_id == project_id)
        if is_active is not None:
            query = query.where(ServiceGroup.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    ServiceGroup.code.ilike(search_pattern),
                    ServiceGroup.name.ilike(search_pattern),
                    ServiceGroup.description.ilike(search_pattern),
                    ServiceProject.name.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(
                sort_column.desc(),
                ServiceProject.sort_order.desc(),
                ServiceGroup.sort_order.desc(),
                ServiceGroup.id.desc(),
            )
        else:
            query = query.order_by(
                sort_column.asc(),
                ServiceProject.sort_order.asc(),
                ServiceGroup.sort_order.asc(),
                ServiceGroup.id.asc(),
            )
        return query


class ServiceQueryBuilder:
    SORT_COLUMNS = {
        "id": Service.id,
        "project_id": ServiceProject.id,
        "group_id": Service.group_id,
        "project_sort_order": ServiceProject.sort_order,
        "group_sort_order": ServiceGroup.sort_order,
        "code": Service.code,
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
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
        )
        if project_id is not None:
            query = query.where(ServiceGroup.project_id == project_id)
        if group_id is not None:
            query = query.where(Service.group_id == group_id)
        if is_active is not None:
            query = query.where(Service.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Service.code.ilike(search_pattern),
                    Service.name.ilike(search_pattern),
                    Service.description.ilike(search_pattern),
                    ServiceGroup.code.ilike(search_pattern),
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

    def get_or_404(self, project_id: int) -> ServiceProject:
        project = self._db_session.get(ServiceProject, project_id)
        if project is None:
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


class ServiceGroupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = ServiceGroupQueryBuilder()

    def create(self, dto: ServiceGroupCreate) -> tuple[ServiceGroup, ServiceProject]:
        project = self._get_project_or_422(project_id=dto.project_id)
        group = ServiceGroup(
            project_id=project.id,
            code=dto.code,
            name=dto.name,
            description=dto.description,
            sort_order=dto.sort_order,
            is_active=True,
        )
        self._db_session.add(group)
        self._commit_with_integrity_guard()
        self._db_session.refresh(group)
        return group, project

    def list(
        self,
        project_id: int | None,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[tuple[ServiceGroup, ServiceProject]], PaginationMeta]:
        query = self._query_builder.build_list_query(
            project_id=project_id,
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
        items = [(row[0], row[1]) for row in rows]
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def get_or_404(self, group_id: int) -> tuple[ServiceGroup, ServiceProject]:
        row = self._db_session.execute(
            select(ServiceGroup, ServiceProject)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(ServiceGroup.id == group_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SERVICE_GROUP_NOT_FOUND,
            )
        return row[0], row[1]

    def update(self, group_id: int, dto: ServiceGroupUpdate) -> tuple[ServiceGroup, ServiceProject]:
        group, _ = self.get_or_404(group_id=group_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        if "project_id" in update_data:
            project_id = update_data["project_id"]
            if project_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=PROJECT_ID_CANNOT_BE_NULL,
                )
            self._get_project_or_422(project_id=project_id)
        for field_name, field_value in update_data.items():
            setattr(group, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(group)
        return self.get_or_404(group_id=group_id)

    def deactivate(self, group_id: int) -> tuple[ServiceGroup, ServiceProject]:
        group, _ = self.get_or_404(group_id=group_id)
        group.is_active = False
        self._db_session.commit()
        self._db_session.refresh(group)
        return self.get_or_404(group_id=group_id)

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


class ServiceCatalogService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = ServiceQueryBuilder()

    def create(self, dto: ServiceCreate) -> tuple[Service, ServiceGroup, ServiceProject]:
        group, project = self._get_group_with_project_or_422(group_id=dto.group_id)
        service = Service(
            group_id=group.id,
            code=dto.code,
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

    def get_or_404(self, service_id: int) -> tuple[Service, ServiceGroup, ServiceProject]:
        row = self._db_session.execute(
            select(Service, ServiceGroup, ServiceProject)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(Service.id == service_id)
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
        if "group_id" in update_data:
            group_id = update_data["group_id"]
            if group_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=GROUP_ID_CANNOT_BE_NULL,
                )
            self._get_group_with_project_or_422(group_id=group_id)
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

    def _get_group_with_project_or_422(self, group_id: int) -> tuple[ServiceGroup, ServiceProject]:
        row = self._db_session.execute(
            select(ServiceGroup, ServiceProject)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(ServiceGroup.id == group_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=GROUP_ID_INVALID,
            )
        return row[0], row[1]

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
        "project_id": ServiceProject.id,
        "project_name": ServiceProject.name,
        "project_sort_order": ServiceProject.sort_order,
        "service_id": Service.id,
        "service_code": Service.code,
        "service_name": Service.name,
        "group_code": ServiceGroup.code,
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
    ) -> Select[tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]]:
        query = (
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(CustomerServiceConfig.customer_id == customer_id)
        )
        if project_id is not None:
            query = query.where(ServiceGroup.project_id == project_id)
        if is_enabled is not None:
            query = query.where(CustomerServiceConfig.is_enabled.is_(is_enabled))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Service.code.ilike(search_pattern),
                    Service.name.ilike(search_pattern),
                    ServiceGroup.code.ilike(search_pattern),
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
    ) -> tuple[list[tuple[CustomerServiceConfig, Service, ServiceGroup, ServiceProject]], PaginationMeta]:
        self._customer_lookup_service.get_or_404(customer_id=customer_id)
        query = self._query_builder.build_list_query(
            customer_id=customer_id,
            project_id=project_id,
            is_enabled=is_enabled,
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
        if "sale_price" in update_data and update_data["sale_price"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=SALE_PRICE_CANNOT_BE_NULL,
            )
        for field_name, field_value in update_data.items():
            setattr(config, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(config)
        row = self._db_session.execute(
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(CustomerServiceConfig.id == config_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_SERVICE_CONFIG_NOT_FOUND,
            )
        return row[0], row[1], row[2], row[3]

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


class CustomerPricingSummaryService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._customer_lookup_service = CustomerLookupService(db_session=db_session)

    def get_summary(self, customer_id: int) -> CustomerPricingSummaryResult:
        customer = self._customer_lookup_service.get_or_404(customer_id=customer_id)
        rows = self._db_session.execute(
            select(CustomerServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == CustomerServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(CustomerServiceConfig.customer_id == customer_id)
            .order_by(
                ServiceProject.sort_order.asc(),
                ServiceGroup.sort_order.asc(),
                Service.sort_order.asc(),
                Service.id.asc(),
            )
        ).all()

        group_bucket: dict[int, CustomerPricingSummaryGroup] = {}
        total_sale = 0
        total_support = 0

        for row in rows:
            config: CustomerServiceConfig = row[0]
            service: Service = row[1]
            group: ServiceGroup = row[2]
            project: ServiceProject = row[3]

            support_price_value = config.support_price or 0
            line_sale_total = config.sale_price if config.is_enabled else 0
            line_support_total = support_price_value if config.is_enabled else 0
            line_grand_total = line_sale_total + line_support_total

            group_entry = group_bucket.get(group.id)
            if group_entry is None:
                group_entry = CustomerPricingSummaryGroup(
                    project_id=project.id,
                    project_name=project.name,
                    group_id=group.id,
                    group_code=group.code,
                    group_name=group.name,
                    items=[],
                    totals=CustomerPricingSummaryGroupTotals(
                        sale_total=0,
                        support_total=0,
                        grand_total=0,
                    ),
                )
                group_bucket[group.id] = group_entry

            group_entry.items.append(
                CustomerPricingSummaryItem(
                    service_id=service.id,
                    service_code=service.code,
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


def get_customer_pricing_summary_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerPricingSummaryService:
    return CustomerPricingSummaryService(db_session=db_session)

