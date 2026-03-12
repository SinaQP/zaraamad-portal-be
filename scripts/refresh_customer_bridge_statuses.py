from app.common.config import get_settings
from app.common.database import database_runtime
from app.common.services.bridge_client import BridgeClient
from app.modules.customers.service import (
    CustomerBridgeConfigService,
    CustomerBridgeService,
    CustomerService,
)


def run() -> None:
    settings = get_settings()
    bridge_client = BridgeClient()
    with database_runtime.session_factory() as session:
        customer_service = CustomerService(db_session=session)
        bridge_config_service = CustomerBridgeConfigService(
            db_session=session,
            customer_service=customer_service,
        )
        bridge_service = CustomerBridgeService(
            bridge_config_service=bridge_config_service,
            bridge_client=bridge_client,
            settings=settings,
        )
        results = bridge_service.refresh_all_statuses()

    if not results:
        print("No refreshable customer bridge configurations found.")
        return

    print(f"Refreshed {len(results)} customer bridge statuses.")
    for customer, bridge_config in results:
        if bridge_config is None:
            print(f"customer_id={customer.id} name={customer.name} status=unknown")
            continue
        status_label = "online" if bridge_config.last_online_status else "offline"
        error_suffix = f" error={bridge_config.last_health_error}" if bridge_config.last_health_error else ""
        print(
            f"customer_id={customer.id} name={customer.name} status={status_label}"
            f" checked_at={bridge_config.last_health_checked_at}{error_suffix}"
        )


if __name__ == "__main__":
    run()
