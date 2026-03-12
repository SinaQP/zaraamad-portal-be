from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
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
    code: Mapped[str] = mapped_column(String(100), nullable=False)
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
    code: Mapped[str] = mapped_column(String(100), nullable=False)
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
        CheckConstraint("sale_price >= 0", name="ck_customer_service_configs_non_negative_sale_price"),
        CheckConstraint(
            "support_price IS NULL OR support_price >= 0",
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
    sale_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    support_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
