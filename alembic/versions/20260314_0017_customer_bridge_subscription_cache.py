"""cache customer bridge subscriptions and drop local subscription resources

Revision ID: 20260314_0017
Revises: 20260314_0016
Create Date: 2026-03-14 16:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260314_0017"
down_revision: str | None = "20260314_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customer_bridge_configs",
        sa.Column("cached_subscription_start_date", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column("cached_subscription_end_date", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column(
            "cached_subscription_grace_period_end_date",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column("cached_subscription_is_active", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column("cached_subscription_status_message", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column("last_subscription_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column("last_subscription_error", sa.String(length=1000), nullable=True),
    )

    op.drop_table("subscription_messages")
    sa.Enum(
        "expired",
        "grace",
        "near_expiry",
        name="subscription_message_status",
    ).drop(op.get_bind(), checkfirst=True)
    op.drop_table("subscriptions")


def downgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("grace_period_end_date", sa.Date(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    subscription_message_status = sa.Enum(
        "expired",
        "grace",
        "near_expiry",
        name="subscription_message_status",
    )
    subscription_message_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "subscription_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("status", subscription_message_status, nullable=False),
        sa.Column("message_template", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("status", name="uq_subscription_messages_status"),
    )

    op.drop_column("customer_bridge_configs", "last_subscription_error")
    op.drop_column("customer_bridge_configs", "last_subscription_synced_at")
    op.drop_column("customer_bridge_configs", "cached_subscription_status_message")
    op.drop_column("customer_bridge_configs", "cached_subscription_is_active")
    op.drop_column("customer_bridge_configs", "cached_subscription_grace_period_end_date")
    op.drop_column("customer_bridge_configs", "cached_subscription_end_date")
    op.drop_column("customer_bridge_configs", "cached_subscription_start_date")
