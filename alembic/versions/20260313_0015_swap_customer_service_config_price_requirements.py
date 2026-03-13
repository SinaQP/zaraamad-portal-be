"""swap customer service config price requirements

Revision ID: 20260313_0015
Revises: 20260312_0014
Create Date: 2026-03-13 12:20:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260313_0015"
down_revision: str | None = "20260312_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE customer_service_configs SET support_price = 0 WHERE support_price IS NULL")
    op.drop_constraint(
        "ck_customer_service_configs_non_negative_sale_price",
        "customer_service_configs",
        type_="check",
    )
    op.drop_constraint(
        "ck_customer_service_configs_non_negative_support_price",
        "customer_service_configs",
        type_="check",
    )
    op.alter_column("customer_service_configs", "sale_price", nullable=True)
    op.alter_column("customer_service_configs", "support_price", nullable=False)
    op.create_check_constraint(
        "ck_customer_service_configs_non_negative_sale_price",
        "customer_service_configs",
        "sale_price IS NULL OR sale_price >= 0",
    )
    op.create_check_constraint(
        "ck_customer_service_configs_non_negative_support_price",
        "customer_service_configs",
        "support_price >= 0",
    )


def downgrade() -> None:
    op.execute("UPDATE customer_service_configs SET sale_price = 0 WHERE sale_price IS NULL")
    op.drop_constraint(
        "ck_customer_service_configs_non_negative_sale_price",
        "customer_service_configs",
        type_="check",
    )
    op.drop_constraint(
        "ck_customer_service_configs_non_negative_support_price",
        "customer_service_configs",
        type_="check",
    )
    op.alter_column("customer_service_configs", "support_price", nullable=True)
    op.alter_column("customer_service_configs", "sale_price", nullable=False)
    op.create_check_constraint(
        "ck_customer_service_configs_non_negative_sale_price",
        "customer_service_configs",
        "sale_price >= 0",
    )
    op.create_check_constraint(
        "ck_customer_service_configs_non_negative_support_price",
        "customer_service_configs",
        "support_price IS NULL OR support_price >= 0",
    )
