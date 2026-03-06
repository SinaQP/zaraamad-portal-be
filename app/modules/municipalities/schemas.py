from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, TimestampMixin


class Municipality(Base, TimestampMixin):
    __tablename__ = "municipalities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    province: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
