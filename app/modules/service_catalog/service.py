from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.database import Base, get_db_session
from app.modules.service_catalog.dtos import (
    MunicipalityPricingSummaryItem,
    MunicipalityPricingSummaryMunicipality,
    MunicipalityPricingSummaryResult,
    MunicipalityPricingSummaryTotals,
    MunicipalityServiceConfigBulkUpsertCreate,
    MunicipalityServiceConfigCreate,
    MunicipalityServiceConfigUpdate,
    ServiceCreate,
    ServiceUpdate,
)
from app.modules.service_catalog.schemas import MunicipalityServiceConfig, Service


class MunicipalityLookupService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def get_or_404(self, municipality_id: int) -> dict[str, int | str]:
        municipality_table = Base.metadata.tables["municipalities"]
        municipality_row = self._db_session.execute(
            select(
                municipality_table.c.id,
                municipality_table.c.name,
                municipality_table.c.code,
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
            "code": municipality_row["code"],
        }


class ServiceCatalogQueryBuilder:
    def build_list_query(self, is_active: bool | None) -> Select[tuple[Service]]:
        query = select(Service).order_by(Service.sort_order.asc(), Service.id.asc())
        if is_active is not None:
            query = query.where(Service.is_active.is_(is_active))
        return query


class ServiceCatalogService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = ServiceCatalogQueryBuilder()

    def create(self, dto: ServiceCreate) -> Service:
        service = Service(
            name=dto.name,
            description=dto.description,
            is_active=True,
            sort_order=dto.sort_order,
        )
        self._db_session.add(service)
        self._commit_with_integrity_guard()
        self._db_session.refresh(service)
        return service

    def list(self, is_active: bool | None) -> list[Service]:
        query = self._query_builder.build_list_query(is_active=is_active)
        return list(self._db_session.scalars(query).all())

    def get_or_404(self, service_id: int) -> Service:
        service = self._db_session.get(Service, service_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )
        return service

    def update(self, service_id: int, dto: ServiceUpdate) -> Service:
        service = self.get_or_404(service_id=service_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(service, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(service)
        return service

    def deactivate(self, service_id: int) -> Service:
        service = self.get_or_404(service_id=service_id)
        service.is_active = False
        self._db_session.commit()
        self._db_session.refresh(service)
        return service

    def _commit_with_integrity_guard(self) -> None:
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Data integrity error.",
            ) from exc


class MunicipalityServiceConfigPolicy:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def validate_payload(self, items: list[MunicipalityServiceConfigCreate]) -> None:
        service_ids = [item.service_id for item in items]
        if len(service_ids) != len(set(service_ids)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="service_id is invalid.",
            )
        if not service.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Inactive service cannot be assigned in new config.",
            )

    def validate_service_exists(self, service: Service | None) -> None:
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )


class MunicipalityServiceConfigService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._municipality_lookup_service = MunicipalityLookupService(db_session=db_session)
        self._policy = MunicipalityServiceConfigPolicy(db_session=db_session)

    def list_by_municipality(
        self,
        municipality_id: int,
    ) -> list[tuple[MunicipalityServiceConfig, Service]]:
        self._municipality_lookup_service.get_or_404(municipality_id=municipality_id)
        return self._list_pairs_by_municipality(municipality_id=municipality_id)

    def bulk_upsert(
        self,
        municipality_id: int,
        dto: MunicipalityServiceConfigBulkUpsertCreate,
    ) -> list[tuple[MunicipalityServiceConfig, Service]]:
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
                    unit_price=item.unit_price,
                    notes=item.notes,
                )
                self._db_session.add(new_config)
                continue
            existing_config.is_enabled = item.is_enabled
            existing_config.unit_price = item.unit_price
            existing_config.notes = item.notes

        self._commit_with_integrity_guard()
        return self._list_pairs_by_municipality(municipality_id=municipality_id)

    def update_single(
        self,
        config_id: int,
        dto: MunicipalityServiceConfigUpdate,
    ) -> tuple[MunicipalityServiceConfig, Service]:
        config = self._db_session.get(MunicipalityServiceConfig, config_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Municipality service config not found.",
            )
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(config, field_name, field_value)
        self._commit_with_integrity_guard()
        self._db_session.refresh(config)
        service = self._db_session.get(Service, config.service_id)
        self._policy.validate_service_exists(service=service)
        return config, service

    def _list_pairs_by_municipality(
        self,
        municipality_id: int,
    ) -> list[tuple[MunicipalityServiceConfig, Service]]:
        rows = self._db_session.execute(
            select(MunicipalityServiceConfig, Service)
            .join(Service, Service.id == MunicipalityServiceConfig.service_id)
            .where(MunicipalityServiceConfig.municipality_id == municipality_id)
            .order_by(Service.sort_order.asc(), Service.id.asc())
        ).all()
        return [(row[0], row[1]) for row in rows]

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
            select(MunicipalityServiceConfig, Service)
            .join(Service, Service.id == MunicipalityServiceConfig.service_id)
            .where(MunicipalityServiceConfig.municipality_id == municipality_id)
            .order_by(Service.sort_order.asc(), Service.id.asc())
        ).all()

        enabled_total = 0
        configured_total = 0
        items: list[MunicipalityPricingSummaryItem] = []

        for row in rows:
            config: MunicipalityServiceConfig = row[0]
            service: Service = row[1]
            line_total = config.unit_price if config.is_enabled else 0
            configured_total += config.unit_price
            items.append(
                MunicipalityPricingSummaryItem(
                    service_id=service.id,
                    service_name=service.name,
                    is_enabled=config.is_enabled,
                    unit_price=config.unit_price,
                    line_total=line_total,
                )
            )
            enabled_total += line_total

        return MunicipalityPricingSummaryResult(
            municipality=MunicipalityPricingSummaryMunicipality(
                id=int(municipality["id"]),
                name=str(municipality["name"]),
                code=str(municipality["code"]),
            ),
            items=items,
            totals=MunicipalityPricingSummaryTotals(
                enabled_total=enabled_total,
                configured_total=configured_total,
            ),
        )


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
