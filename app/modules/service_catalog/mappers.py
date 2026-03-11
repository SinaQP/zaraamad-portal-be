from app.modules.service_catalog.dtos import (
    CustomerServiceConfigOut,
    ServiceGroupInfo,
    ServiceGroupOut,
    ServiceOut,
    ServiceProjectInfo,
    ServiceProjectOut,
)
from app.modules.service_catalog.schemas import CustomerServiceConfig, Service, ServiceGroup, ServiceProject


class ServiceCatalogMapper:
    def to_service_project_out(self, project: ServiceProject) -> ServiceProjectOut:
        return ServiceProjectOut(
            id=project.id,
            name=project.name,
            description=project.description,
            sort_order=project.sort_order,
            is_active=project.is_active,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def to_service_group_out(self, group: ServiceGroup, project: ServiceProject) -> ServiceGroupOut:
        return ServiceGroupOut(
            id=group.id,
            project_id=group.project_id,
            code=group.code,
            name=group.name,
            description=group.description,
            sort_order=group.sort_order,
            project=self.to_service_project_info(project=project),
            is_active=group.is_active,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    def to_service_project_info(self, project: ServiceProject) -> ServiceProjectInfo:
        return ServiceProjectInfo(
            id=project.id,
            name=project.name,
            is_active=project.is_active,
        )

    def to_service_out(self, service: Service, group: ServiceGroup, project: ServiceProject) -> ServiceOut:
        return ServiceOut(
            id=service.id,
            group_id=service.group_id,
            project_id=project.id,
            code=service.code,
            name=service.name,
            description=service.description,
            sort_order=service.sort_order,
            is_active=service.is_active,
            project=self.to_service_project_info(project=project),
            group=ServiceGroupInfo(
                id=group.id,
                project_id=group.project_id,
                code=group.code,
                name=group.name,
                is_active=group.is_active,
            ),
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    def to_customer_config_out(
        self,
        config: CustomerServiceConfig,
        service: Service,
        group: ServiceGroup,
        project: ServiceProject,
    ) -> CustomerServiceConfigOut:
        return CustomerServiceConfigOut(
            id=config.id,
            customer_id=config.customer_id,
            service_id=config.service_id,
            project_id=project.id,
            project_name=project.name,
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
