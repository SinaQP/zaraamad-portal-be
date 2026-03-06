from app.modules.service_catalog.dtos import MunicipalityServiceConfigOut, ServiceGroupInfo, ServiceGroupOut, ServiceOut
from app.modules.service_catalog.schemas import MunicipalityServiceConfig, Service, ServiceGroup


class ServiceCatalogMapper:
    def to_service_group_out(self, group: ServiceGroup) -> ServiceGroupOut:
        return ServiceGroupOut(
            id=group.id,
            code=group.code,
            name=group.name,
            description=group.description,
            sort_order=group.sort_order,
            is_active=group.is_active,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    def to_service_out(self, service: Service, group: ServiceGroup) -> ServiceOut:
        return ServiceOut(
            id=service.id,
            group_id=service.group_id,
            code=service.code,
            name=service.name,
            description=service.description,
            sort_order=service.sort_order,
            is_active=service.is_active,
            group=ServiceGroupInfo(
                id=group.id,
                code=group.code,
                name=group.name,
                is_active=group.is_active,
            ),
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    def to_municipality_config_out(
        self,
        config: MunicipalityServiceConfig,
        service: Service,
        group: ServiceGroup,
    ) -> MunicipalityServiceConfigOut:
        return MunicipalityServiceConfigOut(
            id=config.id,
            municipality_id=config.municipality_id,
            service_id=config.service_id,
            group_id=group.id,
            group_code=group.code,
            group_name=group.name,
            service_code=service.code,
            service_name=service.name,
            service_is_active=service.is_active,
            is_enabled=config.is_enabled,
            sale_price=config.sale_price,
            support_price=config.support_price,
            notes=config.notes,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


def get_service_catalog_mapper() -> ServiceCatalogMapper:
    return ServiceCatalogMapper()
