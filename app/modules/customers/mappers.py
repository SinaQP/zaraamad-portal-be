from app.common.services.bridge_client import BridgeCapabilitiesResult, BridgeHealthResult
from app.modules.customers.dtos import (
    CustomerBridgeCapabilitiesOut,
    CustomerBridgeCapabilityBase,
    CustomerBridgeConfigOut,
    CustomerBridgeHealthOut,
    CustomerBridgeSubscriptionOut,
    CustomerOut,
)
from app.modules.customers.schemas import Customer, CustomerBridgeConfig


class CustomerMapper:
    def to_out(self, customer: Customer) -> CustomerOut:
        return CustomerOut(
            id=customer.id,
            name=customer.name,
            manager_name=customer.manager_name,
            grade=customer.grade,
            is_active=customer.is_active,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )

    def to_bridge_config_out(
        self,
        customer: Customer,
        bridge_config: CustomerBridgeConfig | None,
    ) -> CustomerBridgeConfigOut:
        return CustomerBridgeConfigOut(
            customer_id=customer.id,
            customer_name=customer.name,
            bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
            bridge_is_enabled=bridge_config.bridge_is_enabled if bridge_config else False,
            bridge_has_api_key=bool(bridge_config and bridge_config.bridge_api_key),
            last_online_status=bridge_config.last_online_status if bridge_config else None,
            last_health_checked_at=bridge_config.last_health_checked_at if bridge_config else None,
            last_health_error=bridge_config.last_health_error if bridge_config else None,
        )

    def to_bridge_health_out(
        self,
        customer: Customer,
        bridge_config: CustomerBridgeConfig | None,
        bridge_health: BridgeHealthResult,
    ) -> CustomerBridgeHealthOut:
        return CustomerBridgeHealthOut(
            customer_id=customer.id,
            customer_name=customer.name,
            bridge_base_url=bridge_config.bridge_base_url if bridge_config and bridge_config.bridge_base_url else "",
            status=bridge_health.status,
            bridge_name=bridge_health.bridge_name,
            bridge_version=bridge_health.bridge_version,
        )

    def to_bridge_capabilities_out(
        self,
        customer: Customer,
        bridge_config: CustomerBridgeConfig | None,
        bridge_capabilities: BridgeCapabilitiesResult,
    ) -> CustomerBridgeCapabilitiesOut:
        return CustomerBridgeCapabilitiesOut(
            customer_id=customer.id,
            customer_name=customer.name,
            bridge_base_url=bridge_config.bridge_base_url if bridge_config and bridge_config.bridge_base_url else "",
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

    def to_bridge_subscription_out(
        self,
        customer: Customer,
        bridge_config: CustomerBridgeConfig | None,
    ) -> CustomerBridgeSubscriptionOut:
        return CustomerBridgeSubscriptionOut(
            customer_id=customer.id,
            customer_name=customer.name,
            bridge_base_url=bridge_config.bridge_base_url if bridge_config and bridge_config.bridge_base_url else "",
            start_date=bridge_config.cached_subscription_start_date if bridge_config and bridge_config.cached_subscription_start_date else "",
            end_date=bridge_config.cached_subscription_end_date if bridge_config and bridge_config.cached_subscription_end_date else "",
            grace_period_end_date=bridge_config.cached_subscription_grace_period_end_date if bridge_config else None,
            is_active=bridge_config.cached_subscription_is_active if bridge_config and bridge_config.cached_subscription_is_active is not None else False,
            status_message=bridge_config.cached_subscription_status_message if bridge_config and bridge_config.cached_subscription_status_message is not None else "",
            last_subscription_synced_at=bridge_config.last_subscription_synced_at if bridge_config else None,
            last_subscription_error=bridge_config.last_subscription_error if bridge_config else None,
        )


def get_customer_mapper() -> CustomerMapper:
    return CustomerMapper()
