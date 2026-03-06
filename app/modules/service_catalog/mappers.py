from app.modules.service_catalog.dtos import MunicipalityServiceConfigOut, ServiceOut
from app.modules.service_catalog.schemas import MunicipalityServiceConfig, Service


class ServiceCatalogMapper:
    def to_service_out(self, service: Service) -> ServiceOut:
        return ServiceOut(
            id=service.id,
            name=service.name,
            description=service.description,
            sort_order=service.sort_order,
            is_active=service.is_active,
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    def to_municipality_config_out(
        self,
        config: MunicipalityServiceConfig,
        service: Service,
    ) -> MunicipalityServiceConfigOut:
        return MunicipalityServiceConfigOut(
            id=config.id,
            municipality_id=config.municipality_id,
            service_id=config.service_id,
            service_name=service.name,
            service_is_active=service.is_active,
            is_enabled=config.is_enabled,
            unit_price=config.unit_price,
            notes=config.notes,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


def get_service_catalog_mapper() -> ServiceCatalogMapper:
    return ServiceCatalogMapper()
