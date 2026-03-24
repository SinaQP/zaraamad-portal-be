from datetime import date

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, TimestampMixin


class ServiceProject(Base, TimestampMixin):
    __tablename__ = "service_projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class ServiceGroup(Base, TimestampMixin):
    __tablename__ = "service_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("service_projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("service_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CustomerServiceConfig(Base, TimestampMixin):
    __tablename__ = "customer_service_configs"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "service_id",
            name="uq_customer_service_configs_customer_service",
        ),
        CheckConstraint(
            "sale_price IS NULL OR sale_price >= 0",
            name="ck_customer_service_configs_non_negative_sale_price",
        ),
        CheckConstraint(
            "support_price >= 0",
            name="ck_customer_service_configs_non_negative_support_price",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sale_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    support_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class CustomerServicePurchase(Base, TimestampMixin):
    __tablename__ = "customer_service_purchases"
    __table_args__ = (
        CheckConstraint(
            "sale_total >= 0",
            name="ck_customer_service_purchases_non_negative_sale_total",
        ),
        CheckConstraint(
            "support_total >= 0",
            name="ck_customer_service_purchases_non_negative_support_total",
        ),
        CheckConstraint(
            "grand_total >= 0",
            name="ck_customer_service_purchases_non_negative_grand_total",
        ),
        CheckConstraint(
            "selected_count >= 0",
            name="ck_customer_service_purchases_non_negative_selected_count",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sale_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    support_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    grand_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class CustomerServicePurchaseItem(Base, TimestampMixin):
    __tablename__ = "customer_service_purchase_items"
    __table_args__ = (
        UniqueConstraint(
            "customer_service_purchase_id",
            "customer_service_config_id",
            name="uq_customer_service_purchase_items_purchase_config",
        ),
        CheckConstraint(
            "sale_price IS NULL OR sale_price >= 0",
            name="ck_customer_service_purchase_items_non_negative_sale_price",
        ),
        CheckConstraint(
            "support_price >= 0",
            name="ck_customer_service_purchase_items_non_negative_support_price",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_service_purchase_id: Mapped[int] = mapped_column(
        ForeignKey("customer_service_purchases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_service_config_id: Mapped[int] = mapped_column(
        ForeignKey("customer_service_configs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sale_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    support_price: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CustomerServiceSelectionSnapshot(Base, TimestampMixin):
    __tablename__ = "customer_service_selection_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    selected_at: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text(), nullable=False)
