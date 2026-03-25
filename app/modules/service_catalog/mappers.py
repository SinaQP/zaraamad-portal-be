from app.common.formatters.jalali_datetime import (
    gregorian_date_to_jalali_date_string,
    gregorian_datetime_to_jalali_datetime_string,
    gregorian_datetime_to_time_string,
)
from app.modules.service_catalog.dtos import (
    CustomerServiceConfigOut,
    CustomerServicePurchaseItemOut,
    CustomerServicePurchaseOut,
    CustomerServiceSelectionSnapshotCreateOut,
    CustomerServiceSelectionSnapshotOut,
    ServiceGroupInfo,
    ServiceGroupOut,
    ServiceOut,
    ServiceProjectHierarchyGroupOut,
    ServiceProjectHierarchyProjectOut,
    ServiceProjectHierarchyServiceOut,
    ServiceProjectInfo,
    ServiceProjectOut,
)
from app.modules.service_catalog.schemas import (
    CustomerServiceConfig,
    CustomerServicePurchase,
    CustomerServicePurchaseItem,
    CustomerServiceSelectionSnapshot,
    Service,
    ServiceGroup,
    ServiceProject,
)


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

    def to_service_group_info(self, group: ServiceGroup) -> ServiceGroupInfo:
        return ServiceGroupInfo(
            id=group.id,
            name=group.name,
            is_active=group.is_active,
        )

    def to_service_group_out(self, group: ServiceGroup) -> ServiceGroupOut:
        return ServiceGroupOut(
            id=group.id,
            name=group.name,
            description=group.description,
            sort_order=group.sort_order,
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
            project_id=service.project_id,
            group_id=service.group_id,
            name=service.name,
            description=service.description,
            sort_order=service.sort_order,
            is_active=service.is_active,
            project=self.to_service_project_info(project=project),
            group=self.to_service_group_info(group=group),
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    def to_service_project_hierarchy_service_out(self, service: Service) -> ServiceProjectHierarchyServiceOut:
        return ServiceProjectHierarchyServiceOut(
            id=service.id,
            name=service.name,
            description=service.description,
            sort_order=service.sort_order,
            is_active=service.is_active,
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    def to_service_project_hierarchy_group_out(
        self,
        group: ServiceGroup,
        services: list[Service],
    ) -> ServiceProjectHierarchyGroupOut:
        group_out = self.to_service_group_out(group=group)
        return ServiceProjectHierarchyGroupOut(
            **group_out.model_dump(),
            services=[
                self.to_service_project_hierarchy_service_out(service=item)
                for item in services
            ],
        )

    def to_service_project_hierarchy_project_out(
        self,
        project: ServiceProject,
        groups: list[tuple[ServiceGroup, list[Service]]],
    ) -> ServiceProjectHierarchyProjectOut:
        project_out = self.to_service_project_out(project=project)
        return ServiceProjectHierarchyProjectOut(
            **project_out.model_dump(),
            groups=[
                self.to_service_project_hierarchy_group_out(group=group, services=services)
                for group, services in groups
            ],
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
            group_name=group.name,
            service_name=service.name,
            service_is_active=service.is_active,
            is_enabled=config.is_enabled,
            sale_price=config.sale_price,
            support_price=config.support_price,
            notes=config.notes,
            created_at=config.created_at,
            updated_at=gregorian_datetime_to_jalali_datetime_string(config.updated_at),
        )

    def to_customer_service_purchase_item_out(
        self,
        item: CustomerServicePurchaseItem,
    ) -> CustomerServicePurchaseItemOut:
        sale_price = item.sale_price
        line_sale_total = sale_price or 0
        line_support_total = item.support_price
        return CustomerServicePurchaseItemOut(
            id=item.id,
            customer_service_config_id=item.customer_service_config_id,
            service_id=item.service_id,
            project_id=item.project_id,
            project_name=item.project_name,
            group_id=item.group_id,
            group_name=item.group_name,
            service_name=item.service_name,
            sale_price=sale_price,
            support_price=item.support_price,
            line_sale_total=line_sale_total,
            line_support_total=line_support_total,
            line_grand_total=line_sale_total + line_support_total,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def to_customer_service_purchase_out(
        self,
        purchase: CustomerServicePurchase,
        items: list[CustomerServicePurchaseItem],
    ) -> CustomerServicePurchaseOut:
        return CustomerServicePurchaseOut(
            id=purchase.id,
            customer_id=purchase.customer_id,
            created_by_user_id=purchase.created_by_user_id,
            notes=purchase.notes,
            selected_count=purchase.selected_count,
            sale_total=purchase.sale_total,
            support_total=purchase.support_total,
            grand_total=purchase.grand_total,
            is_active=purchase.is_active,
            items=[
                self.to_customer_service_purchase_item_out(item=item)
                for item in items
            ],
            created_at=purchase.created_at,
            updated_at=purchase.updated_at,
        )

    def to_customer_service_selection_snapshot_out(
        self,
        snapshot: CustomerServiceSelectionSnapshot,
        *,
        customer_name: str,
        user_name: str,
    ) -> CustomerServiceSelectionSnapshotOut:
        return CustomerServiceSelectionSnapshotOut(
            id=snapshot.id,
            customer_id=snapshot.customer_id,
            customer_name=customer_name,
            user_id=snapshot.user_id,
            user_name=user_name,
            date=gregorian_date_to_jalali_date_string(snapshot.selected_at),
            time=gregorian_datetime_to_time_string(snapshot.created_at),
            payload=snapshot.payload,
        )

    def to_customer_service_selection_snapshot_create_out(
        self,
        snapshot: CustomerServiceSelectionSnapshot,
    ) -> CustomerServiceSelectionSnapshotCreateOut:
        return CustomerServiceSelectionSnapshotCreateOut(
            id=snapshot.id,
            customer_id=snapshot.customer_id,
            user_id=snapshot.user_id,
            date=gregorian_date_to_jalali_date_string(snapshot.selected_at),
            time=gregorian_datetime_to_time_string(snapshot.created_at),
            payload=snapshot.payload,
        )


def get_service_catalog_mapper() -> ServiceCatalogMapper:
    return ServiceCatalogMapper()
