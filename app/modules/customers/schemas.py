from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
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
