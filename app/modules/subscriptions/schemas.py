from datetime import date

from sqlalchemy import Boolean, Date, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, TimestampMixin
from app.common.enums import SubscriptionMessageStatus


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    grace_period_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class SubscriptionMessage(Base, TimestampMixin):
    __tablename__ = "subscription_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[SubscriptionMessageStatus] = mapped_column(
        Enum(
            SubscriptionMessageStatus,
            name="subscription_message_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        unique=True,
    )
    message_template: Mapped[str] = mapped_column(String(1000), nullable=False)
