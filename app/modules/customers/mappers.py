from app.common.services.bridge_client import BridgeCapabilitiesResult, BridgeHealthResult
from app.modules.customers.dtos import (
    CustomerBridgeCapabilitiesOut,
    CustomerBridgeCapabilityBase,
    CustomerBridgeHealthOut,
    CustomerOut,
)
from app.modules.customers.schemas import Customer


class CustomerMapper:
    def to_out(self, customer: Customer) -> CustomerOut:
        return CustomerOut(
            id=customer.id,
            name=customer.name,
            grade=customer.grade,
            bridge_base_url=customer.bridge_base_url,
            bridge_is_enabled=customer.bridge_is_enabled,
            bridge_has_api_key=bool(customer.bridge_api_key),
            is_active=customer.is_active,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )

    def to_bridge_health_out(
        self,
        customer: Customer,
        bridge_health: BridgeHealthResult,
    ) -> CustomerBridgeHealthOut:
        return CustomerBridgeHealthOut(
            customer_id=customer.id,
            customer_name=customer.name,
            bridge_base_url=customer.bridge_base_url or "",
            status=bridge_health.status,
            bridge_name=bridge_health.bridge_name,
            bridge_version=bridge_health.bridge_version,
        )

    def to_bridge_capabilities_out(
        self,
        customer: Customer,
        bridge_capabilities: BridgeCapabilitiesResult,
    ) -> CustomerBridgeCapabilitiesOut:
        return CustomerBridgeCapabilitiesOut(
            customer_id=customer.id,
            customer_name=customer.name,
            bridge_base_url=customer.bridge_base_url or "",
            bridge_name=bridge_capabilities.bridge_name,
            bridge_version=bridge_capabilities.bridge_version,
            capabilities=[
                CustomerBridgeCapabilityBase(
                    code=item.code,
                    name=item.name,
                    description=item.description,
                )
                for item in bridge_capabilities.capabilities
            ],
        )


def get_customer_mapper() -> CustomerMapper:
    return CustomerMapper()
