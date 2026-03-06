from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, TimestampMixin


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MunicipalityServiceConfig(Base, TimestampMixin):
    __tablename__ = "municipality_service_configs"
    __table_args__ = (
        UniqueConstraint(
            "municipality_id",
            "service_id",
            name="uq_municipality_service_configs_municipality_service",
        ),
        CheckConstraint("unit_price >= 0", name="ck_municipality_service_configs_non_negative_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipalities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
