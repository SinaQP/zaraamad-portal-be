from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    manager_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class CustomerBridgeConfig(Base, TimestampMixin):
    __tablename__ = "customer_bridge_configs"

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bridge_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bridge_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bridge_is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    last_online_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cached_subscription_start_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cached_subscription_end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cached_subscription_grace_period_end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cached_subscription_is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cached_subscription_status_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_subscription_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_subscription_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class CustomerIncomeSummary(Base, TimestampMixin):
    __tablename__ = "customer_income_summaries"

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    registered_income_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    issued_bill_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paid_bill_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collection_rate_percent: Mapped[float | None] = mapped_column(Float, nullable=True)


class CustomerIncomeBucket(Base, TimestampMixin):
    __tablename__ = "customer_income_buckets"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "bucket_code",
            name="uq_customer_income_buckets_customer_bucket_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bucket_code: Mapped[str] = mapped_column(String(50), nullable=False)
    bucket_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registered_income_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CustomerIncomeMonthlyReport(Base, TimestampMixin):
    __tablename__ = "customer_income_monthly_reports"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "month",
            name="uq_customer_income_monthly_reports_customer_month",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    registered_income_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    issued_bill_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paid_bill_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collection_rate_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
