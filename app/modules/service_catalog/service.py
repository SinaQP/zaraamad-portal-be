from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.common.enums import SortOrder
from app.common.pagination import PaginationMeta, PaginationParams
from app.modules.service_catalog.dtos import (
    MunicipalityPricingSummaryGroup,
    MunicipalityPricingSummaryGroupTotals,
    MunicipalityPricingSummaryItem,
    MunicipalityPricingSummaryMunicipality,
    MunicipalityPricingSummaryResult,
    MunicipalityPricingSummaryTotals,
    MunicipalityServiceConfigBulkUpsertCreate,
    MunicipalityServiceConfigCreate,
    MunicipalityServiceConfigUpdate,
    ServiceCreate,
    ServiceGroupCreate,
    ServiceGroupUpdate,
    ServiceProjectCreate,
    ServiceProjectUpdate,
    ServiceUpdate,
)
from app.modules.service_catalog.schemas import MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject


class MunicipalityLookupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_or_404(self, municipality_id: int) -> dict[str, int | str]:
        municipality_table = Base.metadata.tables["municipalities"]
        municipality_row = self._db_session.execute(
            select(
                municipality_table.c.id,
                municipality_table.c.name,
                municipality_table.c.grade,
            ).where(municipality_table.c.id == municipality_id)
        ).mappings().first()
        if municipality_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Municipality not found.",
            )
        return {
            "id": municipality_row["id"],
            "name": municipality_row["name"],
            "grade": municipality_row["grade"],
        }


class ServiceProjectQueryBuilder:
    SORT_COLUMNS = {
        "id": ServiceProject.id,
        "code": ServiceProject.code,
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
                    ServiceProject.code.ilike(search_pattern),
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
                    ServiceProject.code.ilike(search_pattern),
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
                    ServiceProject.code.ilike(search_pattern),
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
            code=dto.code,
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
                detail="Service project not found.",
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
                detail="Data integrity error.",
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
                detail="Service group not found.",
            )
        return row[0], row[1]

    def update(self, group_id: int, dto: ServiceGroupUpdate) -> tuple[ServiceGroup, ServiceProject]:
        group, _ = self.get_or_404(group_id=group_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        if "project_id" in update_data:
            project_id = update_data["project_id"]
            if project_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="project_id cannot be null.",
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="project_id is invalid.",
            )
        return project

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Data integrity error.",
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
                detail="Service not found.",
            )
        return row[0], row[1], row[2]

    def update(self, service_id: int, dto: ServiceUpdate) -> tuple[Service, ServiceGroup, ServiceProject]:
        service, _, _ = self.get_or_404(service_id=service_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        if "group_id" in update_data:
            group_id = update_data["group_id"]
            if group_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="group_id cannot be null.",
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="group_id is invalid.",
            )
        return row[0], row[1]

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Data integrity error.",
            ) from exc


class MunicipalityServiceConfigQueryBuilder:
    SORT_COLUMNS = {
        "id": MunicipalityServiceConfig.id,
        "project_id": ServiceProject.id,
        "project_code": ServiceProject.code,
        "project_name": ServiceProject.name,
        "project_sort_order": ServiceProject.sort_order,
        "service_id": Service.id,
        "service_code": Service.code,
        "service_name": Service.name,
        "group_code": ServiceGroup.code,
        "group_name": ServiceGroup.name,
        "group_sort_order": ServiceGroup.sort_order,
        "service_sort_order": Service.sort_order,
        "is_enabled": MunicipalityServiceConfig.is_enabled,
        "sale_price": MunicipalityServiceConfig.sale_price,
        "support_price": MunicipalityServiceConfig.support_price,
        "created_at": MunicipalityServiceConfig.created_at,
        "updated_at": MunicipalityServiceConfig.updated_at,
    }

    def build_list_query(
        self,
        municipality_id: int,
        project_id: int | None,
        is_enabled: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject]]:
        query = (
            select(MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == MunicipalityServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(MunicipalityServiceConfig.municipality_id == municipality_id)
        )
        if project_id is not None:
            query = query.where(ServiceGroup.project_id == project_id)
        if is_enabled is not None:
            query = query.where(MunicipalityServiceConfig.is_enabled.is_(is_enabled))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Service.code.ilike(search_pattern),
                    Service.name.ilike(search_pattern),
                    ServiceGroup.code.ilike(search_pattern),
                    ServiceGroup.name.ilike(search_pattern),
                    ServiceProject.code.ilike(search_pattern),
                    ServiceProject.name.ilike(search_pattern),
                    MunicipalityServiceConfig.notes.ilike(search_pattern),
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


class MunicipalityServiceConfigPolicy:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def validate_payload(self, items: list[MunicipalityServiceConfigCreate]) -> None:
        service_ids = [item.service_id for item in items]
        if len(service_ids) != len(set(service_ids)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Duplicate service_id in payload is not allowed.",
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
        municipality_id: int,
        service_ids: list[int],
    ) -> dict[int, MunicipalityServiceConfig]:
        existing_configs = list(
            self._db_session.scalars(
                select(MunicipalityServiceConfig).where(
                    MunicipalityServiceConfig.municipality_id == municipality_id,
                    MunicipalityServiceConfig.service_id.in_(service_ids),
                )
            ).all()
        )
        return {config.service_id: config for config in existing_configs}

    def validate_service_for_create(self, service: Service | None) -> None:
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="service_id is invalid.",
            )
        if not service.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Inactive service cannot be assigned in new config.",
            )


class MunicipalityServiceConfigService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._municipality_lookup_service = MunicipalityLookupService(db_session=db_session)
        self._policy = MunicipalityServiceConfigPolicy(db_session=db_session)
        self._query_builder = MunicipalityServiceConfigQueryBuilder()

    def list_by_municipality(
        self,
        municipality_id: int,
        project_id: int | None,
        is_enabled: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[tuple[MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject]], PaginationMeta]:
        self._municipality_lookup_service.get_or_404(municipality_id=municipality_id)
        query = self._query_builder.build_list_query(
            municipality_id=municipality_id,
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
        municipality_id: int,
        dto: MunicipalityServiceConfigBulkUpsertCreate,
    ) -> list[tuple[MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject]]:
        self._municipality_lookup_service.get_or_404(municipality_id=municipality_id)
        self._policy.validate_payload(items=dto.items)

        service_ids = [item.service_id for item in dto.items]
        service_map = self._policy.get_service_map(service_ids=service_ids)
        existing_config_map = self._policy.get_existing_config_map(
            municipality_id=municipality_id,
            service_ids=service_ids,
        )

        for item in dto.items:
            existing_config = existing_config_map.get(item.service_id)
            service = service_map.get(item.service_id)
            if existing_config is None:
                self._policy.validate_service_for_create(service=service)
                new_config = MunicipalityServiceConfig(
                    municipality_id=municipality_id,
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
        return self._list_joined_configs(municipality_id=municipality_id)

    def update_single(
        self,
        config_id: int,
        dto: MunicipalityServiceConfigUpdate,
    ) -> tuple[MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject]:
        config = self._db_session.get(MunicipalityServiceConfig, config_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Municipality service config not found.",
            )
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        if "sale_price" in update_data and update_data["sale_price"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="sale_price cannot be null.",
            )
        for field_name, field_value in update_data.items():
            setattr(config, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(config)
        row = self._db_session.execute(
            select(MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == MunicipalityServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(MunicipalityServiceConfig.id == config_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Municipality service config not found.",
            )
        return row[0], row[1], row[2], row[3]

    def _list_joined_configs(
        self,
        municipality_id: int,
    ) -> list[tuple[MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject]]:
        rows = self._db_session.execute(
            self._query_builder.build_list_query(
                municipality_id=municipality_id,
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
            if "municipality_service_configs" in error_text or "service_id" in error_text:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Duplicate municipality/service configuration is not allowed.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Data integrity error.",
            ) from exc


class MunicipalityPricingSummaryService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._municipality_lookup_service = MunicipalityLookupService(db_session=db_session)

    def get_summary(self, municipality_id: int) -> MunicipalityPricingSummaryResult:
        municipality = self._municipality_lookup_service.get_or_404(municipality_id=municipality_id)
        rows = self._db_session.execute(
            select(MunicipalityServiceConfig, Service, ServiceGroup, ServiceProject)
            .join(Service, Service.id == MunicipalityServiceConfig.service_id)
            .join(ServiceGroup, ServiceGroup.id == Service.group_id)
            .join(ServiceProject, ServiceProject.id == ServiceGroup.project_id)
            .where(MunicipalityServiceConfig.municipality_id == municipality_id)
            .order_by(
                ServiceProject.sort_order.asc(),
                ServiceGroup.sort_order.asc(),
                Service.sort_order.asc(),
                Service.id.asc(),
            )
        ).all()

        group_bucket: dict[int, MunicipalityPricingSummaryGroup] = {}
        total_sale = 0
        total_support = 0

        for row in rows:
            config: MunicipalityServiceConfig = row[0]
            service: Service = row[1]
            group: ServiceGroup = row[2]
            project: ServiceProject = row[3]

            support_price_value = config.support_price or 0
            line_sale_total = config.sale_price if config.is_enabled else 0
            line_support_total = support_price_value if config.is_enabled else 0
            line_grand_total = line_sale_total + line_support_total

            group_entry = group_bucket.get(group.id)
            if group_entry is None:
                group_entry = MunicipalityPricingSummaryGroup(
                    project_id=project.id,
                    project_code=project.code,
                    project_name=project.name,
                    group_id=group.id,
                    group_code=group.code,
                    group_name=group.name,
                    items=[],
                    totals=MunicipalityPricingSummaryGroupTotals(
                        sale_total=0,
                        support_total=0,
                        grand_total=0,
                    ),
                )
                group_bucket[group.id] = group_entry

            group_entry.items.append(
                MunicipalityPricingSummaryItem(
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
        return MunicipalityPricingSummaryResult(
            municipality=MunicipalityPricingSummaryMunicipality(
                id=int(municipality["id"]),
                name=str(municipality["name"]),
                grade=int(municipality["grade"]),
            ),
            groups=groups,
            totals=MunicipalityPricingSummaryTotals(
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


def get_municipality_service_config_service(
    db_session: Session = Depends(get_db_session),
) -> MunicipalityServiceConfigService:
    return MunicipalityServiceConfigService(db_session=db_session)


def get_municipality_pricing_summary_service(
    db_session: Session = Depends(get_db_session),
) -> MunicipalityPricingSummaryService:
    return MunicipalityPricingSummaryService(db_session=db_session)
