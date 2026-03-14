"""add customer service purchases

Revision ID: 20260314_0016
Revises: 20260313_0015
Create Date: 2026-03-14 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260314_0016"
down_revision: str | None = "20260313_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_service_purchases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("sale_total", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("support_total", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("grand_total", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("selected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "sale_total >= 0",
            name="ck_customer_service_purchases_non_negative_sale_total",
        ),
        sa.CheckConstraint(
            "support_total >= 0",
            name="ck_customer_service_purchases_non_negative_support_total",
        ),
        sa.CheckConstraint(
            "grand_total >= 0",
            name="ck_customer_service_purchases_non_negative_grand_total",
        ),
        sa.CheckConstraint(
            "selected_count >= 0",
            name="ck_customer_service_purchases_non_negative_selected_count",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_customer_service_purchases_customer_id"),
        "customer_service_purchases",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_service_purchases_created_by_user_id"),
        "customer_service_purchases",
        ["created_by_user_id"],
        unique=False,
    )

    op.create_table(
        "customer_service_purchase_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_service_purchase_id", sa.Integer(), nullable=False),
        sa.Column("customer_service_config_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=False),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("sale_price", sa.BigInteger(), nullable=True),
        sa.Column("support_price", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "sale_price IS NULL OR sale_price >= 0",
            name="ck_customer_service_purchase_items_non_negative_sale_price",
        ),
        sa.CheckConstraint(
            "support_price >= 0",
            name="ck_customer_service_purchase_items_non_negative_support_price",
        ),
        sa.ForeignKeyConstraint(
            ["customer_service_purchase_id"],
            ["customer_service_purchases.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_service_config_id"],
            ["customer_service_configs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_service_purchase_id",
            "customer_service_config_id",
            name="uq_customer_service_purchase_items_purchase_config",
        ),
    )
    op.create_index(
        op.f("ix_customer_service_purchase_items_customer_service_purchase_id"),
        "customer_service_purchase_items",
        ["customer_service_purchase_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_service_purchase_items_customer_service_config_id"),
        "customer_service_purchase_items",
        ["customer_service_config_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_customer_service_purchase_items_customer_service_config_id"),
        table_name="customer_service_purchase_items",
    )
    op.drop_index(
        op.f("ix_customer_service_purchase_items_customer_service_purchase_id"),
        table_name="customer_service_purchase_items",
    )
    op.drop_table("customer_service_purchase_items")

    op.drop_index(
        op.f("ix_customer_service_purchases_created_by_user_id"),
        table_name="customer_service_purchases",
    )
    op.drop_index(
        op.f("ix_customer_service_purchases_customer_id"),
        table_name="customer_service_purchases",
    )
    op.drop_table("customer_service_purchases")
