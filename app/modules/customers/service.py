from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, HTTPException, status
from openpyxl import load_workbook
from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.common.database import get_db_session
from app.common.dtos import CurrentUser
from app.common.enums import SortOrder, UserRole
from app.common.messages import (
    CUSTOMER_ACCESS_DENIED,
    CUSTOMER_BRIDGE_AUTH_FAILED,
    CUSTOMER_BRIDGE_INVALID_RESPONSE,
    CUSTOMER_BRIDGE_NOT_CONFIGURED,
    CUSTOMER_BRIDGE_REQUEST_FAILED,
    CUSTOMER_BRIDGE_SUBSCRIPTION_NOT_CACHED,
    CUSTOMER_BRIDGE_UNAVAILABLE,
    CUSTOMER_INCOME_NOT_FOUND,
    CUSTOMER_NOT_FOUND,
    DATA_INTEGRITY_ERROR,
)
from app.common.pagination import PaginationMeta, PaginationParams
from app.common.services.bridge_client import (
    BridgeCapabilitiesResult,
    BridgeClient,
    BridgeConnectionError,
    BridgeHealthResult,
    BridgeSubscriptionConfigResult,
    BridgeSubscriptionMessageResult,
    BridgeSubscriptionResult,
    BridgeInvalidResponseError,
    BridgeRequest,
    BridgeUnauthorizedError,
    BridgeUnexpectedStatusError,
    get_bridge_client,
)
from app.modules.customers.dtos import CustomerBridgeConfigUpdate, CustomerCreate, CustomerUpdate
from app.modules.customers.schemas import (
    Customer,
    CustomerBridgeConfig,
    CustomerIncomeBucket,
    CustomerIncomeSummary,
)


class CustomerQueryBuilder:
    SORT_COLUMNS = {
        "id": Customer.id,
        "name": Customer.name,
        "manager_name": Customer.manager_name,
        "grade": Customer.grade,
        "is_active": Customer.is_active,
        "created_at": Customer.created_at,
        "updated_at": Customer.updated_at,
    }

    def build_list_query(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Customer]]:
        query = select(Customer)
        if is_active is None:
            query = query.where(Customer.is_active.is_(True))
        else:
            query = query.where(Customer.is_active.is_(is_active))
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Customer.name.ilike(search_pattern),
                    Customer.manager_name.ilike(search_pattern),
                )
            )
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), Customer.id.desc())
        else:
            query = query.order_by(sort_column.asc(), Customer.id.asc())
        return query


class CustomerService:
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._query_builder = CustomerQueryBuilder()

    def create(self, dto: CustomerCreate) -> Customer:
        customer = Customer(
            name=dto.name,
            manager_name=dto.manager_name,
            grade=dto.grade,
            is_active=True,
        )
        self._db_session.add(customer)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(customer)
        return customer

    def list_customers(
        self,
        is_active: bool | None,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[Customer], PaginationMeta]:
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

    def list_all(self) -> list[Customer]:
        query = (
            select(Customer)
            .where(Customer.is_active.is_(True))
            .order_by(Customer.id.asc())
        )
        return list(self._db_session.scalars(query).all())

    def get_or_404(self, customer_id: int) -> Customer:
        customer = self._db_session.get(Customer, customer_id)
        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_NOT_FOUND,
            )
        return customer

    def get_active_or_404(self, customer_id: int) -> Customer:
        customer = self.get_or_404(customer_id=customer_id)
        if not customer.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_NOT_FOUND,
            )
        return customer

    def update(self, customer_id: int, dto: CustomerUpdate) -> Customer:
        customer = self.get_or_404(customer_id=customer_id)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(customer, field_name, field_value)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(customer)
        return customer

    def deactivate(self, customer_id: int) -> Customer:
        customer = self.get_or_404(customer_id=customer_id)
        customer.is_active = False
        self._db_session.commit()
        self._db_session.refresh(customer)
        return customer


class CustomerBridgeConfigService:
    def __init__(
        self,
        db_session: Session,
        customer_service: CustomerService,
    ) -> None:
        self._db_session = db_session
        self._customer_service = customer_service

    def get(self, customer_id: int) -> tuple[Customer, CustomerBridgeConfig | None]:
        customer = self._customer_service.get_or_404(customer_id=customer_id)
        bridge_config = self._db_session.get(CustomerBridgeConfig, customer_id)
        return customer, bridge_config

    def get_active(self, customer_id: int) -> tuple[Customer, CustomerBridgeConfig | None]:
        customer = self._customer_service.get_active_or_404(customer_id=customer_id)
        bridge_config = self._db_session.get(CustomerBridgeConfig, customer_id)
        return customer, bridge_config

    def upsert(
        self,
        customer_id: int,
        dto: CustomerBridgeConfigUpdate,
    ) -> tuple[Customer, CustomerBridgeConfig]:
        customer, bridge_config = self.get(customer_id=customer_id)
        if bridge_config is None:
            bridge_config = CustomerBridgeConfig(customer_id=customer_id)
            self._db_session.add(bridge_config)
        update_data = dto.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, field_value in update_data.items():
            setattr(bridge_config, field_name, field_value)
        if update_data:
            self.clear_health_status(bridge_config=bridge_config)
            self.clear_subscription_cache(bridge_config=bridge_config)
        try:
            self._db_session.commit()
        except IntegrityError as exc:
            self._db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DATA_INTEGRITY_ERROR,
            ) from exc
        self._db_session.refresh(bridge_config)
        return customer, bridge_config

    def clear_health_status(self, bridge_config: CustomerBridgeConfig) -> None:
        bridge_config.last_online_status = None
        bridge_config.last_health_checked_at = None
        bridge_config.last_health_error = None

    def clear_subscription_cache(self, bridge_config: CustomerBridgeConfig) -> None:
        bridge_config.cached_subscription_start_date = None
        bridge_config.cached_subscription_end_date = None
        bridge_config.cached_subscription_grace_period_end_date = None
        bridge_config.cached_subscription_is_active = None
        bridge_config.cached_subscription_status_message = None
        bridge_config.last_subscription_synced_at = None
        bridge_config.last_subscription_error = None

    def persist_health_status(
        self,
        bridge_config: CustomerBridgeConfig,
        *,
        is_online: bool,
        checked_at: datetime,
        error: str | None,
    ) -> CustomerBridgeConfig:
        bridge_config.last_online_status = is_online
        bridge_config.last_health_checked_at = checked_at
        bridge_config.last_health_error = error
        self._db_session.commit()
        self._db_session.refresh(bridge_config)
        return bridge_config

    def persist_subscription_snapshot(
        self,
        bridge_config: CustomerBridgeConfig,
        *,
        subscription: BridgeSubscriptionResult,
        checked_at: datetime,
    ) -> CustomerBridgeConfig:
        bridge_config.cached_subscription_start_date = subscription.start_date
        bridge_config.cached_subscription_end_date = subscription.end_date
        bridge_config.cached_subscription_grace_period_end_date = subscription.grace_period_end_date
        bridge_config.cached_subscription_is_active = subscription.is_active
        bridge_config.cached_subscription_status_message = subscription.status_message
        bridge_config.last_subscription_synced_at = checked_at
        bridge_config.last_subscription_error = None
        self._db_session.commit()
        self._db_session.refresh(bridge_config)
        return bridge_config

    def persist_subscription_absence(
        self,
        bridge_config: CustomerBridgeConfig,
        *,
        checked_at: datetime,
        error: str,
    ) -> CustomerBridgeConfig:
        self.clear_subscription_cache(bridge_config=bridge_config)
        bridge_config.last_subscription_synced_at = checked_at
        bridge_config.last_subscription_error = error
        self._db_session.commit()
        self._db_session.refresh(bridge_config)
        return bridge_config

    def persist_subscription_refresh_error(
        self,
        bridge_config: CustomerBridgeConfig,
        *,
        error: str,
    ) -> CustomerBridgeConfig:
        bridge_config.last_subscription_error = error
        self._db_session.commit()
        self._db_session.refresh(bridge_config)
        return bridge_config

    def list_refreshable_customer_ids(self) -> list[int]:
        query = (
            select(CustomerBridgeConfig.customer_id)
            .where(CustomerBridgeConfig.bridge_is_enabled.is_(True))
            .where(CustomerBridgeConfig.bridge_base_url.is_not(None))
            .where(CustomerBridgeConfig.bridge_base_url != "")
            .where(CustomerBridgeConfig.bridge_api_key.is_not(None))
            .where(CustomerBridgeConfig.bridge_api_key != "")
            .order_by(CustomerBridgeConfig.customer_id.asc())
        )
        return list(self._db_session.scalars(query).all())


DEFAULT_IMPORTED_CUSTOMER_GRADE = 1


@dataclass(frozen=True)
class ImportedCustomerIncomeSummary:
    customer_name: str
    registered_income_amount_12m: int | None
    issued_bills_count_12m: int | None
    paid_bills_count_12m: int | None
    collection_rate_percent_12m: float | None


@dataclass(frozen=True)
class ImportedCustomerIncomeBucket:
    customer_name: str
    bucket_code: str
    chart_label: str | None
    registered_income_amount_12m: int | None


@dataclass(frozen=True)
class CustomerIncomeValidationFailure:
    customer_name: str
    message: str
    summary_registered_income_amount_12m: int | None
    bucket_total_registered_income_amount_12m: int | None


@dataclass(frozen=True)
class CustomerIncomeWorkbookData:
    summaries: list[ImportedCustomerIncomeSummary]
    buckets: list[ImportedCustomerIncomeBucket]
    validation_failures: list[CustomerIncomeValidationFailure]


@dataclass(frozen=True)
class CustomerIncomeImportReport:
    processed_customer_count: int
    upserted_summary_count: int
    upserted_bucket_count: int
    validation_failures: list[CustomerIncomeValidationFailure]


class CustomerIncomeQueryBuilder:
    SORT_COLUMNS = {
        "customer_name": Customer.name,
        "registered_income_amount_12m": CustomerIncomeSummary.registered_income_amount_12m,
        "issued_bills_count_12m": CustomerIncomeSummary.issued_bills_count_12m,
        "paid_bills_count_12m": CustomerIncomeSummary.paid_bills_count_12m,
        "collection_rate_percent_12m": CustomerIncomeSummary.collection_rate_percent_12m,
        "created_at": CustomerIncomeSummary.created_at,
        "updated_at": CustomerIncomeSummary.updated_at,
    }

    def build_list_query(
        self,
        *,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
    ) -> Select[tuple[Customer, CustomerIncomeSummary]]:
        query = (
            select(Customer, CustomerIncomeSummary)
            .join(CustomerIncomeSummary, CustomerIncomeSummary.customer_id == Customer.id)
            .where(Customer.is_active.is_(True))
        )
        if search:
            search_pattern = f"%{search}%"
            query = query.where(Customer.name.ilike(search_pattern))
        sort_column = self.SORT_COLUMNS[sort_by]
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc(), Customer.id.desc())
        else:
            query = query.order_by(sort_column.asc(), Customer.id.asc())
        return query


class CustomerScopedAccessPolicy:
    def validate_customer_access(
        self,
        *,
        current_user: CurrentUser,
        customer_id: int,
    ) -> None:
        if current_user.role == UserRole.ADMIN:
            return
        has_customer_access = (
            current_user.role == UserRole.CUSTOMER
            and current_user.customer_id == customer_id
        )
        if has_customer_access:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": CUSTOMER_ACCESS_DENIED,
                "developer_message": (
                    f"User {current_user.id} with role {current_user.role.value} "
                    f"cannot access customer {customer_id}."
                ),
            },
        )


class CustomerIncomeService:
    def __init__(
        self,
        db_session: Session,
        customer_service: CustomerService,
    ) -> None:
        self._db_session = db_session
        self._customer_service = customer_service
        self._query_builder = CustomerIncomeQueryBuilder()
        self._access_policy = CustomerScopedAccessPolicy()

    def list_summaries(
        self,
        *,
        search: str | None,
        sort_by: str,
        sort_order: SortOrder,
        pagination: PaginationParams,
    ) -> tuple[list[tuple[Customer, CustomerIncomeSummary]], PaginationMeta]:
        query = self._query_builder.build_list_query(
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
        items = list(self._db_session.execute(paginated_query).all())
        meta = PaginationMeta(
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        return items, meta

    def get_detail(
        self,
        *,
        customer_id: int,
        current_user: CurrentUser,
    ) -> tuple[Customer, CustomerIncomeSummary, list[CustomerIncomeBucket]]:
        customer = self._customer_service.get_active_or_404(customer_id=customer_id)
        self._access_policy.validate_customer_access(
            current_user=current_user,
            customer_id=customer.id,
        )
        income_summary = self._db_session.get(CustomerIncomeSummary, customer.id)
        if income_summary is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=CUSTOMER_INCOME_NOT_FOUND,
            )
        bucket_query = (
            select(CustomerIncomeBucket)
            .where(CustomerIncomeBucket.customer_id == customer.id)
            .order_by(
                CustomerIncomeBucket.bucket_code.asc(),
                CustomerIncomeBucket.id.asc(),
            )
        )
        buckets = list(self._db_session.scalars(bucket_query).all())
        return customer, income_summary, buckets


class CustomerIncomeImportService:
    SUMMARY_HEADER_FALLBACKS = {
        "registered_income_amount_12m": 0,
        "issued_bills_count_12m": 1,
        "paid_bills_count_12m": 2,
        "collection_rate_percent_12m": 3,
    }

    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def import_workbook(
        self,
        *,
        workbook_path: str | Path,
    ) -> CustomerIncomeImportReport:
        workbook_data = self.parse_workbook(workbook_path=workbook_path)
        summaries_by_name = {
            item.customer_name: item
            for item in workbook_data.summaries
        }
        buckets_by_name: dict[str, list[ImportedCustomerIncomeBucket]] = {}
        for bucket in workbook_data.buckets:
            buckets_by_name.setdefault(bucket.customer_name, []).append(bucket)

        customer_names = sorted(set(summaries_by_name) | set(buckets_by_name))
        upserted_summary_count = 0
        upserted_bucket_count = 0

        try:
            for customer_name in customer_names:
                customer = self._get_or_create_customer(customer_name=customer_name)
                summary_row = summaries_by_name.get(customer_name)
                income_summary = self._db_session.get(CustomerIncomeSummary, customer.id)
                if income_summary is None:
                    income_summary = CustomerIncomeSummary(customer_id=customer.id)
                    self._db_session.add(income_summary)
                income_summary.registered_income_amount_12m = (
                    summary_row.registered_income_amount_12m if summary_row else None
                )
                income_summary.issued_bills_count_12m = (
                    summary_row.issued_bills_count_12m if summary_row else None
                )
                income_summary.paid_bills_count_12m = (
                    summary_row.paid_bills_count_12m if summary_row else None
                )
                income_summary.collection_rate_percent_12m = (
                    summary_row.collection_rate_percent_12m if summary_row else None
                )
                upserted_summary_count += 1

                self._db_session.execute(
                    delete(CustomerIncomeBucket).where(
                        CustomerIncomeBucket.customer_id == customer.id
                    )
                )
                customer_buckets = buckets_by_name.get(customer_name, [])
                for bucket_row in customer_buckets:
                    self._db_session.add(
                        CustomerIncomeBucket(
                            customer_id=customer.id,
                            bucket_code=bucket_row.bucket_code,
                            chart_label=bucket_row.chart_label,
                            registered_income_amount_12m=bucket_row.registered_income_amount_12m,
                        )
                    )
                upserted_bucket_count += len(customer_buckets)
            self._db_session.commit()
        except Exception:
            self._db_session.rollback()
            raise

        return CustomerIncomeImportReport(
            processed_customer_count=len(customer_names),
            upserted_summary_count=upserted_summary_count,
            upserted_bucket_count=upserted_bucket_count,
            validation_failures=workbook_data.validation_failures,
        )

    def parse_workbook(
        self,
        *,
        workbook_path: str | Path,
    ) -> CustomerIncomeWorkbookData:
        workbook_file = Path(workbook_path)
        if not workbook_file.exists():
            raise FileNotFoundError(f"Workbook not found: {workbook_file}")

        workbook = load_workbook(filename=workbook_file, data_only=True)
        try:
            summary_sheet = self._get_sheet(workbook=workbook, sheet_name="Sheet1", fallback_index=0)
            bucket_sheet = self._get_sheet(workbook=workbook, sheet_name="Sheet2", fallback_index=1)
            summaries = self._parse_summary_sheet(sheet=summary_sheet)
            buckets = self._parse_bucket_sheet(sheet=bucket_sheet)
        finally:
            workbook.close()

        return CustomerIncomeWorkbookData(
            summaries=summaries,
            buckets=buckets,
            validation_failures=self._build_validation_failures(
                summaries=summaries,
                buckets=buckets,
            ),
        )

    def _get_or_create_customer(self, *, customer_name: str) -> Customer:
        customer = self._db_session.scalar(
            select(Customer)
            .where(Customer.name == customer_name)
            .order_by(Customer.id.asc())
            .limit(1)
        )
        if customer is not None:
            if not customer.is_active:
                customer.is_active = True
            return customer
        customer = Customer(
            name=customer_name,
            manager_name=None,
            grade=DEFAULT_IMPORTED_CUSTOMER_GRADE,
            is_active=True,
        )
        self._db_session.add(customer)
        self._db_session.flush()
        return customer

    def _get_sheet(self, *, workbook, sheet_name: str, fallback_index: int):
        if sheet_name in workbook.sheetnames:
            return workbook[sheet_name]
        if len(workbook.worksheets) <= fallback_index:
            raise ValueError(f"Worksheet '{sheet_name}' was not found in workbook.")
        return workbook.worksheets[fallback_index]

    def _parse_summary_sheet(self, *, sheet) -> list[ImportedCustomerIncomeSummary]:
        rows = list(sheet.iter_rows(values_only=True))
        if len(rows) <= 1:
            return []

        data_rows = rows[1:]
        municipality_name_index = self._detect_summary_name_column(data_rows=data_rows)
        header_lookup = {
            self._normalize_text(header).lower(): index
            for index, header in enumerate(rows[0])
            if self._normalize_text(header) is not None
        }
        parsed_rows: list[ImportedCustomerIncomeSummary] = []
        for row in data_rows:
            customer_name = self._normalize_text(
                row[municipality_name_index] if municipality_name_index < len(row) else None
            )
            if customer_name is None:
                continue
            parsed_rows.append(
                ImportedCustomerIncomeSummary(
                    customer_name=customer_name,
                    registered_income_amount_12m=self._parse_int(
                        self._value_from_row(
                            row=row,
                            header_lookup=header_lookup,
                            field_name="registered_income_amount_12m",
                        )
                    ),
                    issued_bills_count_12m=self._parse_int(
                        self._value_from_row(
                            row=row,
                            header_lookup=header_lookup,
                            field_name="issued_bills_count_12m",
                        )
                    ),
                    paid_bills_count_12m=self._parse_int(
                        self._value_from_row(
                            row=row,
                            header_lookup=header_lookup,
                            field_name="paid_bills_count_12m",
                        )
                    ),
                    collection_rate_percent_12m=self._parse_float(
                        self._value_from_row(
                            row=row,
                            header_lookup=header_lookup,
                            field_name="collection_rate_percent_12m",
                        )
                    ),
                )
            )
        return parsed_rows

    def _parse_bucket_sheet(self, *, sheet) -> list[ImportedCustomerIncomeBucket]:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []

        current_customer_name = self._normalize_text(
            rows[0][3] if len(rows[0]) > 3 else None
        )
        raw_rows: list[ImportedCustomerIncomeBucket] = []
        for row in rows:
            if self._is_blank_row(row=row):
                current_customer_name = None
                continue
            row_customer_name = self._normalize_text(row[3] if len(row) > 3 else None)
            if row_customer_name is not None:
                current_customer_name = row_customer_name
            bucket_code = self._normalize_bucket_code(row[0] if len(row) > 0 else None)
            if bucket_code is None or bucket_code.lower() == "bucket_code":
                continue
            if current_customer_name is None:
                continue
            raw_rows.append(
                ImportedCustomerIncomeBucket(
                    customer_name=current_customer_name,
                    bucket_code=bucket_code,
                    chart_label=self._normalize_text(row[1] if len(row) > 1 else None),
                    registered_income_amount_12m=self._parse_int(row[2] if len(row) > 2 else None),
                )
            )

        canonical_labels = self._build_canonical_bucket_labels(bucket_rows=raw_rows)
        return [
            ImportedCustomerIncomeBucket(
                customer_name=item.customer_name,
                bucket_code=item.bucket_code,
                chart_label=self._resolve_chart_label(
                    raw_label=item.chart_label,
                    canonical_label=canonical_labels.get(item.bucket_code),
                ),
                registered_income_amount_12m=item.registered_income_amount_12m,
            )
            for item in raw_rows
        ]

    def _build_validation_failures(
        self,
        *,
        summaries: list[ImportedCustomerIncomeSummary],
        buckets: list[ImportedCustomerIncomeBucket],
    ) -> list[CustomerIncomeValidationFailure]:
        summaries_by_name = {
            item.customer_name: item
            for item in summaries
        }
        bucket_customer_names = {item.customer_name for item in buckets}
        bucket_totals: dict[str, int] = {}
        for bucket in buckets:
            if bucket.registered_income_amount_12m is None:
                continue
            bucket_totals[bucket.customer_name] = (
                bucket_totals.get(bucket.customer_name, 0)
                + bucket.registered_income_amount_12m
            )

        failures: list[CustomerIncomeValidationFailure] = []
        for customer_name in sorted(set(summaries_by_name) | bucket_customer_names):
            summary_row = summaries_by_name.get(customer_name)
            summary_amount = (
                summary_row.registered_income_amount_12m
                if summary_row is not None
                else None
            )
            bucket_total = bucket_totals.get(customer_name)
            if summary_row is None and customer_name in bucket_customer_names:
                failures.append(
                    CustomerIncomeValidationFailure(
                        customer_name=customer_name,
                        message="Summary row missing in Sheet1.",
                        summary_registered_income_amount_12m=None,
                        bucket_total_registered_income_amount_12m=bucket_total,
                    )
                )
                continue
            if summary_row is not None and customer_name not in bucket_customer_names:
                failures.append(
                    CustomerIncomeValidationFailure(
                        customer_name=customer_name,
                        message="Bucket breakdown rows missing in Sheet2.",
                        summary_registered_income_amount_12m=summary_amount,
                        bucket_total_registered_income_amount_12m=None,
                    )
                )
                continue
            if summary_amount is not None and bucket_total is not None and summary_amount != bucket_total:
                failures.append(
                    CustomerIncomeValidationFailure(
                        customer_name=customer_name,
                        message="Bucket total does not match summary registered income.",
                        summary_registered_income_amount_12m=summary_amount,
                        bucket_total_registered_income_amount_12m=bucket_total,
                    )
                )
        return failures

    def _detect_summary_name_column(self, *, data_rows: list[tuple[object, ...]]) -> int:
        candidate_index = -1
        max_length = max((len(row) for row in data_rows), default=0)
        for index in range(max_length):
            has_text_value = any(
                self._is_textual_value(row[index] if index < len(row) else None)
                for row in data_rows
            )
            if has_text_value:
                candidate_index = index
        if candidate_index >= 0:
            return candidate_index
        return 4

    def _value_from_row(
        self,
        *,
        row: tuple[object, ...],
        header_lookup: dict[str, int],
        field_name: str,
    ) -> object | None:
        column_index = header_lookup.get(
            field_name,
            self.SUMMARY_HEADER_FALLBACKS[field_name],
        )
        if column_index >= len(row):
            return None
        return row[column_index]

    def _build_canonical_bucket_labels(
        self,
        *,
        bucket_rows: list[ImportedCustomerIncomeBucket],
    ) -> dict[str, str]:
        canonical_labels: dict[str, str] = {}
        for row in bucket_rows:
            if row.chart_label is None or self._is_numeric_like(row.chart_label):
                continue
            canonical_labels.setdefault(row.bucket_code, row.chart_label)
        return canonical_labels

    def _resolve_chart_label(
        self,
        *,
        raw_label: str | None,
        canonical_label: str | None,
    ) -> str | None:
        if raw_label is None or self._is_numeric_like(raw_label):
            return canonical_label or raw_label
        return raw_label

    def _normalize_bucket_code(self, value: object | None) -> str | None:
        normalized_text = self._normalize_text(value)
        if normalized_text is None:
            return None
        if self._is_numeric_like(normalized_text):
            parsed_value = self._parse_int(normalized_text)
            if parsed_value is not None:
                return str(parsed_value)
        return normalized_text.upper()

    def _normalize_text(self, value: object | None) -> str | None:
        if value is None:
            return None
        text_value = str(value).strip()
        if not text_value:
            return None
        return text_value

    def _parse_int(self, value: object | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        try:
            return int(Decimal(str(value).replace(",", "").strip()))
        except (InvalidOperation, ValueError):
            return None

    def _parse_float(self, value: object | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(Decimal(str(value).replace(",", "").strip()))
        except (InvalidOperation, ValueError):
            return None

    def _is_blank_row(self, *, row: tuple[object, ...]) -> bool:
        return all(self._normalize_text(value) is None for value in row)

    def _is_textual_value(self, value: object | None) -> bool:
        normalized_text = self._normalize_text(value)
        if normalized_text is None:
            return False
        return not self._is_numeric_like(normalized_text)

    def _is_numeric_like(self, value: object | None) -> bool:
        normalized_text = self._normalize_text(value)
        if normalized_text is None:
            return False
        try:
            Decimal(normalized_text.replace(",", ""))
        except InvalidOperation:
            return False
        return True


@dataclass(frozen=True)
class ResolvedCustomerBridgeConfig:
    base_url: str
    api_key: str
    timeout_seconds: int


class CustomerBridgeConfigResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(
        self,
        customer: Customer,
        bridge_config: CustomerBridgeConfig | None,
    ) -> ResolvedCustomerBridgeConfig:
        missing_fields: list[str] = []
        if bridge_config is None or not bridge_config.bridge_is_enabled:
            missing_fields.append("bridge_is_enabled")
        if bridge_config is None or not bridge_config.bridge_base_url:
            missing_fields.append("bridge_base_url")
        if bridge_config is None or not bridge_config.bridge_api_key:
            missing_fields.append("bridge_api_key")
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": CUSTOMER_BRIDGE_NOT_CONFIGURED,
                    "developer_message": (
                        f"Customer {customer.id} bridge configuration is incomplete. "
                        f"Missing or disabled fields: {', '.join(missing_fields)}."
                    ),
                },
            )
        return ResolvedCustomerBridgeConfig(
            base_url=bridge_config.bridge_base_url,
            api_key=bridge_config.bridge_api_key,
            timeout_seconds=self._settings.bridge_request_timeout_seconds,
        )


class CustomerBridgeService:
    def __init__(
        self,
        bridge_config_service: CustomerBridgeConfigService,
        bridge_client: BridgeClient,
        settings: Settings,
    ) -> None:
        self._bridge_config_service = bridge_config_service
        self._bridge_client = bridge_client
        self._config_resolver = CustomerBridgeConfigResolver(settings=settings)

    def get_health(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeHealthResult]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            bridge_health = self._bridge_client.get_health(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            if bridge_config is not None:
                bridge_config = self._bridge_config_service.persist_health_status(
                    bridge_config=bridge_config,
                    is_online=False,
                    checked_at=checked_at,
                    error=self._build_health_error_message(exc),
                )
            raise self._map_bridge_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_health_status(
                bridge_config=bridge_config,
                is_online=True,
                checked_at=checked_at,
                error=None,
            )
        return customer, bridge_config, bridge_health

    def refresh_status(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            self._bridge_client.get_health(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            if bridge_config is not None:
                bridge_config = self._bridge_config_service.persist_health_status(
                    bridge_config=bridge_config,
                    is_online=False,
                    checked_at=checked_at,
                    error=self._build_health_error_message(exc),
                )
            return customer, bridge_config
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_health_status(
                bridge_config=bridge_config,
                is_online=True,
                checked_at=checked_at,
                error=None,
            )
        return customer, bridge_config

    def get_capabilities(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeCapabilitiesResult]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        try:
            bridge_capabilities = self._bridge_client.get_capabilities(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            raise self._map_bridge_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        return customer, bridge_config, bridge_capabilities

    def fetch_active_subscription(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeSubscriptionResult]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            bridge_subscription = self._bridge_client.get_active_subscription(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            self._handle_subscription_bridge_error(
                bridge_config=bridge_config,
                checked_at=checked_at,
                exc=exc,
            )
            raise self._map_subscription_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_subscription_snapshot(
                bridge_config=bridge_config,
                subscription=bridge_subscription,
                checked_at=checked_at,
            )
        return customer, bridge_config, bridge_subscription

    def update_bridge_subscription(
        self,
        customer_id: int,
        payload: dict[str, object],
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeSubscriptionResult]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            bridge_subscription = self._bridge_client.update_active_subscription(
                request=request,
                payload=payload,
            )
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            self._handle_subscription_bridge_error(
                bridge_config=bridge_config,
                checked_at=checked_at,
                exc=exc,
            )
            raise self._map_subscription_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_subscription_snapshot(
                bridge_config=bridge_config,
                subscription=bridge_subscription,
                checked_at=checked_at,
            )
        return customer, bridge_config, bridge_subscription

    def get_subscription_messages(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, list[BridgeSubscriptionMessageResult]]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        try:
            bridge_messages = self._bridge_client.get_subscription_messages(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            raise self._map_bridge_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        return customer, bridge_config, bridge_messages

    def upsert_subscription_messages(
        self,
        customer_id: int,
        payload: list[dict[str, object]],
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, list[BridgeSubscriptionMessageResult]]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        try:
            bridge_messages = self._bridge_client.upsert_subscription_messages(
                request=request,
                payload=payload,
            )
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            raise self._map_bridge_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        return customer, bridge_config, bridge_messages

    def get_subscription_config(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeSubscriptionConfigResult]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            bridge_config_result = self._bridge_client.get_subscription_config(request=request)
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            self._handle_subscription_bridge_error(
                bridge_config=bridge_config,
                checked_at=checked_at,
                exc=exc,
            )
            raise self._map_subscription_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_subscription_snapshot(
                bridge_config=bridge_config,
                subscription=bridge_config_result.subscription,
                checked_at=checked_at,
            )
        return customer, bridge_config, bridge_config_result

    def sync_subscription_config(
        self,
        customer_id: int,
        payload: dict[str, object],
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeSubscriptionConfigResult]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            bridge_config_result = self._bridge_client.sync_subscription_config(
                request=request,
                payload=payload,
            )
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            self._handle_subscription_bridge_error(
                bridge_config=bridge_config,
                checked_at=checked_at,
                exc=exc,
            )
            raise self._map_subscription_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_subscription_snapshot(
                bridge_config=bridge_config,
                subscription=bridge_config_result.subscription,
                checked_at=checked_at,
            )
        return customer, bridge_config, bridge_config_result

    def get_subscription(
        self,
        customer_id: int,
    ) -> tuple[Customer, CustomerBridgeConfig]:
        customer, bridge_config = self._bridge_config_service.get_active(customer_id=customer_id)
        self._config_resolver.resolve(
            customer=customer,
            bridge_config=bridge_config,
        )
        if bridge_config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": CUSTOMER_BRIDGE_SUBSCRIPTION_NOT_CACHED,
                    "developer_message": (
                        f"Customer {customer.id} does not have a bridge configuration record."
                    ),
                },
            )
        has_cached_subscription = (
            bridge_config.cached_subscription_start_date is not None
            and bridge_config.cached_subscription_end_date is not None
            and bridge_config.cached_subscription_is_active is not None
        )
        if has_cached_subscription:
            return customer, bridge_config
        cached_message = (
            bridge_config.last_subscription_error
            or CUSTOMER_BRIDGE_SUBSCRIPTION_NOT_CACHED
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": cached_message,
                "developer_message": (
                    f"Customer {customer.id} does not have a cached bridge subscription. "
                    "Run the subscription refresh endpoint first."
                ),
            },
        )

    def refresh_subscription(
        self,
        customer_id: int,
        correlation_id: str | None = None,
    ) -> tuple[Customer, CustomerBridgeConfig | None]:
        customer, bridge_config, request = self._build_request(
            customer_id=customer_id,
            correlation_id=correlation_id,
        )
        checked_at = datetime.now(timezone.utc)
        try:
            bridge_subscription = self._bridge_client.get_active_subscription(
                request=request,
            )
        except (
            BridgeConnectionError,
            BridgeUnauthorizedError,
            BridgeUnexpectedStatusError,
            BridgeInvalidResponseError,
        ) as exc:
            if bridge_config is not None:
                if (
                    isinstance(exc, BridgeUnexpectedStatusError)
                    and exc.status_code == status.HTTP_404_NOT_FOUND
                ):
                    bridge_config = self._bridge_config_service.persist_subscription_absence(
                        bridge_config=bridge_config,
                        checked_at=checked_at,
                        error=self._build_subscription_error_message(exc),
                    )
                else:
                    bridge_config = self._bridge_config_service.persist_subscription_refresh_error(
                        bridge_config=bridge_config,
                        error=self._build_subscription_error_message(exc),
                    )
            raise self._map_subscription_error(
                customer=customer,
                bridge_base_url=bridge_config.bridge_base_url if bridge_config else None,
                exc=exc,
            ) from exc
        if bridge_config is not None:
            bridge_config = self._bridge_config_service.persist_subscription_snapshot(
                bridge_config=bridge_config,
                subscription=bridge_subscription,
                checked_at=checked_at,
            )
        return customer, bridge_config

    def _build_request(
        self,
        customer_id: int,
        correlation_id: str | None,
    ) -> tuple[Customer, CustomerBridgeConfig | None, BridgeRequest]:
        customer, bridge_config = self._bridge_config_service.get_active(customer_id=customer_id)
        resolved_bridge_config = self._config_resolver.resolve(
            customer=customer,
            bridge_config=bridge_config,
        )
        return customer, bridge_config, BridgeRequest(
            base_url=resolved_bridge_config.base_url,
            api_key=resolved_bridge_config.api_key,
            timeout_seconds=resolved_bridge_config.timeout_seconds,
            correlation_id=correlation_id,
        )

    def _map_bridge_error(
        self,
        customer: Customer,
        bridge_base_url: str | None,
        exc: (
            BridgeConnectionError
            | BridgeUnauthorizedError
            | BridgeUnexpectedStatusError
            | BridgeInvalidResponseError
        ),
    ) -> HTTPException:
        if isinstance(exc, BridgeConnectionError):
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": CUSTOMER_BRIDGE_UNAVAILABLE,
                    "developer_message": (
                        f"Bridge request for customer {customer.id} could not reach "
                        f"{bridge_base_url}: {exc}"
                    ),
                },
            )
        if isinstance(exc, BridgeUnauthorizedError):
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": CUSTOMER_BRIDGE_AUTH_FAILED,
                    "developer_message": (
                        f"Bridge request for customer {customer.id} was rejected with "
                        f"status {exc.status_code}."
                    ),
                },
            )
        if isinstance(exc, BridgeUnexpectedStatusError):
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": CUSTOMER_BRIDGE_REQUEST_FAILED,
                    "developer_message": (
                        f"Bridge request for customer {customer.id} returned "
                        f"unexpected status {exc.status_code}."
                    ),
                },
            )
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": CUSTOMER_BRIDGE_INVALID_RESPONSE,
                "developer_message": (
                    f"Bridge response for customer {customer.id} did not match the "
                    f"expected schema: {exc}"
                ),
            },
        )

    def refresh_all_statuses(self) -> list[tuple[Customer, CustomerBridgeConfig | None]]:
        results: list[tuple[Customer, CustomerBridgeConfig | None]] = []
        for customer_id in self._bridge_config_service.list_refreshable_customer_ids():
            results.append(self.refresh_status(customer_id=customer_id))
        return results

    def _map_subscription_error(
        self,
        customer: Customer,
        bridge_base_url: str | None,
        exc: (
            BridgeConnectionError
            | BridgeUnauthorizedError
            | BridgeUnexpectedStatusError
            | BridgeInvalidResponseError
        ),
    ) -> HTTPException:
        if (
            isinstance(exc, BridgeUnexpectedStatusError)
            and exc.status_code == status.HTTP_404_NOT_FOUND
        ):
            upstream_message = (
                self._extract_bridge_error_message(response_body=exc.response_body)
                or "هیچ اشتراک فعالی وجود ندارد."
            )
            return HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": upstream_message,
                    "developer_message": (
                        f"Bridge subscription request for customer {customer.id} "
                        f"at {bridge_base_url} returned status 404."
                    ),
                },
            )
        return self._map_bridge_error(
            customer=customer,
            bridge_base_url=bridge_base_url,
            exc=exc,
        )

    def _build_health_error_message(
        self,
        exc: (
            BridgeConnectionError
            | BridgeUnauthorizedError
            | BridgeUnexpectedStatusError
            | BridgeInvalidResponseError
        ),
    ) -> str:
        return str(exc)

    def _build_subscription_error_message(
        self,
        exc: (
            BridgeConnectionError
            | BridgeUnauthorizedError
            | BridgeUnexpectedStatusError
            | BridgeInvalidResponseError
        ),
    ) -> str:
        if isinstance(exc, BridgeConnectionError):
            return CUSTOMER_BRIDGE_UNAVAILABLE
        if isinstance(exc, BridgeUnauthorizedError):
            return CUSTOMER_BRIDGE_AUTH_FAILED
        if isinstance(exc, BridgeUnexpectedStatusError):
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                return (
                    self._extract_bridge_error_message(response_body=exc.response_body)
                    or "هیچ اشتراک فعالی وجود ندارد."
                )
            return CUSTOMER_BRIDGE_REQUEST_FAILED
        return CUSTOMER_BRIDGE_INVALID_RESPONSE

    def _handle_subscription_bridge_error(
        self,
        bridge_config: CustomerBridgeConfig | None,
        checked_at: datetime,
        exc: (
            BridgeConnectionError
            | BridgeUnauthorizedError
            | BridgeUnexpectedStatusError
            | BridgeInvalidResponseError
        ),
    ) -> None:
        if bridge_config is None:
            return
        if isinstance(exc, BridgeUnexpectedStatusError) and exc.status_code == status.HTTP_404_NOT_FOUND:
            self._bridge_config_service.persist_subscription_absence(
                bridge_config=bridge_config,
                checked_at=checked_at,
                error=self._build_subscription_error_message(exc),
            )
            return
        self._bridge_config_service.persist_subscription_refresh_error(
            bridge_config=bridge_config,
            error=self._build_subscription_error_message(exc),
        )

    def _extract_bridge_error_message(self, response_body: str | None) -> str | None:
        if not response_body:
            return None
        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        for field_name in ("error", "message", "detail"):
            field_value = payload.get(field_name)
            if isinstance(field_value, str) and field_value.strip():
                return field_value.strip()
        return None


def get_customer_service(
    db_session: Session = Depends(get_db_session),
) -> CustomerService:
    return CustomerService(db_session=db_session)


def get_customer_income_service(
    db_session: Session = Depends(get_db_session),
    customer_service: CustomerService = Depends(get_customer_service),
) -> CustomerIncomeService:
    return CustomerIncomeService(
        db_session=db_session,
        customer_service=customer_service,
    )


def get_customer_bridge_config_service(
    db_session: Session = Depends(get_db_session),
    customer_service: CustomerService = Depends(get_customer_service),
) -> CustomerBridgeConfigService:
    return CustomerBridgeConfigService(
        db_session=db_session,
        customer_service=customer_service,
    )


def get_customer_bridge_service(
    customer_bridge_config_service: CustomerBridgeConfigService = Depends(get_customer_bridge_config_service),
    bridge_client: BridgeClient = Depends(get_bridge_client),
    settings: Settings = Depends(get_settings),
) -> CustomerBridgeService:
    return CustomerBridgeService(
        bridge_config_service=customer_bridge_config_service,
        bridge_client=bridge_client,
        settings=settings,
    )
