from app.common.services.bridge_client import BridgeCapabilitiesResult, BridgeHealthResult
from app.common.formatters.jalali_datetime import gregorian_datetime_to_jalali_datetime_string
from app.modules.customers.dtos import (
    CustomerBridgeCapabilitiesOut,
    CustomerBridgeCapabilityBase,
    CustomerBridgeConfigOut,
    CustomerBridgeHealthOut,
    CustomerBridgeSubscriptionOut,
    CustomerDatabaseConnectionOut,
    CustomerIncomeBucketOut,
    CustomerIncomeCustomerOut,
    CustomerIncomeDetailOut,
    CustomerIncomeListCustomerOut,
    CustomerIncomeListItemOut,
    CustomerIncomeMonthlyReportOut,
    CustomerIncomeSummaryOut,
    CustomerOut,
)
from app.modules.customers.schemas import (
    Customer,
    CustomerBridgeConfig,
    CustomerDatabaseConnection,
    CustomerIncomeBucket,
    CustomerIncomeMonthlyReport,
    CustomerIncomeSummary,
)


class CustomerMapper:
    def to_out(self, customer: Customer) -> CustomerOut:
        return CustomerOut(
            id=customer.id,
            name=customer.name,
            manager_name=customer.manager_name,
            grade=customer.grade,
            is_active=customer.is_active,
            created_at=customer.created_at,
            updated_at=gregorian_datetime_to_jalali_datetime_string(customer.updated_at),
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

    def to_database_connection_out(
        self,
        customer: Customer,
        database_connection: CustomerDatabaseConnection | None,
    ) -> CustomerDatabaseConnectionOut | None:
        if database_connection is None:
            return None
        return CustomerDatabaseConnectionOut(
            customer_id=customer.id,
            customer_name=customer.name,
            db_kind=database_connection.db_kind,
            is_active=database_connection.is_active,
            has_connection_secret=bool(
                database_connection.encrypted_connection_string
                or database_connection.secret_ref
            ),
            secret_version=database_connection.secret_version,
            credential_rotated_at=database_connection.credential_rotated_at,
            rotation_due_at=database_connection.rotation_due_at,
            last_connection_tested_at=database_connection.last_connection_tested_at,
            last_connection_test_success=database_connection.last_connection_test_success,
            last_connection_error=database_connection.last_connection_error,
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

    def to_income_summary_out(
        self,
        income_summary: CustomerIncomeSummary,
    ) -> CustomerIncomeSummaryOut:
        return CustomerIncomeSummaryOut(
            registered_income_amount=income_summary.registered_income_amount,
            issued_bill_count=income_summary.issued_bill_count,
            paid_bill_count=income_summary.paid_bill_count,
            collection_rate_percent=income_summary.collection_rate_percent,
            created_at=income_summary.created_at,
            updated_at=income_summary.updated_at,
        )

    def to_income_list_item_out(
        self,
        customer: Customer,
        income_summary: CustomerIncomeSummary,
    ) -> CustomerIncomeListItemOut:
        return CustomerIncomeListItemOut(
            customer=CustomerIncomeListCustomerOut(
                id=customer.id,
                name=customer.name,
            ),
            summary=self.to_income_summary_out(income_summary=income_summary),
        )

    def to_income_bucket_out(
        self,
        bucket: CustomerIncomeBucket,
    ) -> CustomerIncomeBucketOut:
        return CustomerIncomeBucketOut(
            bucket_code=bucket.bucket_code,
            bucket_name=bucket.bucket_name,
            registered_income_amount=bucket.registered_income_amount,
        )

    def to_income_monthly_report_out(
        self,
        monthly_report: CustomerIncomeMonthlyReport,
    ) -> CustomerIncomeMonthlyReportOut:
        return CustomerIncomeMonthlyReportOut(
            month=monthly_report.month,
            registered_income_amount=monthly_report.registered_income_amount,
            issued_bill_count=monthly_report.issued_bill_count,
            paid_bill_count=monthly_report.paid_bill_count,
            collection_rate_percent=monthly_report.collection_rate_percent,
        )

    def to_income_detail_out(
        self,
        customer: Customer,
        income_summary: CustomerIncomeSummary | None,
        buckets: list[CustomerIncomeBucket],
        monthly_reports: list[CustomerIncomeMonthlyReport],
    ) -> CustomerIncomeDetailOut:
        return CustomerIncomeDetailOut(
            customer=CustomerIncomeCustomerOut(
                id=customer.id,
                name=customer.name,
                manager_name=customer.manager_name,
                grade=customer.grade,
            ),
            summary=(
                self.to_income_summary_out(income_summary=income_summary)
                if income_summary is not None
                else None
            ),
            buckets=[self.to_income_bucket_out(bucket=item) for item in buckets],
            monthly_reports=[
                self.to_income_monthly_report_out(monthly_report=item)
                for item in monthly_reports
            ],
        )


def get_customer_mapper() -> CustomerMapper:
    return CustomerMapper()
