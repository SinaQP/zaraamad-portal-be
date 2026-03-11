"""rename municipality entities to customer

Revision ID: 20260311_0008
Revises: 20260310_0007
Create Date: 2026-03-11 15:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260311_0008"
down_revision: str | None = "20260310_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("municipalities", "customers")
    op.execute("ALTER TABLE customers RENAME CONSTRAINT municipalities_pkey TO customers_pkey")
    op.execute("ALTER SEQUENCE municipalities_id_seq RENAME TO customers_id_seq")

    op.execute("ALTER TABLE users RENAME COLUMN municipality_id TO customer_id")
    op.execute("ALTER TABLE users RENAME CONSTRAINT ck_users_role_municipality TO ck_users_role_customer")
    op.execute("ALTER TABLE users RENAME CONSTRAINT users_municipality_id_fkey TO users_customer_id_fkey")

    op.rename_table("municipality_service_configs", "customer_service_configs")
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "municipality_service_configs_pkey TO customer_service_configs_pkey"
    )
    op.execute("ALTER SEQUENCE municipality_service_configs_id_seq RENAME TO customer_service_configs_id_seq")
    op.execute("ALTER TABLE customer_service_configs RENAME COLUMN municipality_id TO customer_id")
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "uq_municipality_service_configs_municipality_service TO uq_customer_service_configs_customer_service"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "ck_municipality_service_configs_non_negative_sale_price "
        "TO ck_customer_service_configs_non_negative_sale_price"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "ck_municipality_service_configs_non_negative_support_price "
        "TO ck_customer_service_configs_non_negative_support_price"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "municipality_service_configs_municipality_id_fkey TO customer_service_configs_customer_id_fkey"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "municipality_service_configs_service_id_fkey TO customer_service_configs_service_id_fkey"
    )
    op.execute(
        "ALTER INDEX ix_municipality_service_configs_municipality_id "
        "RENAME TO ix_customer_service_configs_customer_id"
    )
    op.execute(
        "ALTER INDEX ix_municipality_service_configs_service_id "
        "RENAME TO ix_customer_service_configs_service_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_customer_service_configs_service_id "
        "RENAME TO ix_municipality_service_configs_service_id"
    )
    op.execute(
        "ALTER INDEX ix_customer_service_configs_customer_id "
        "RENAME TO ix_municipality_service_configs_municipality_id"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "customer_service_configs_service_id_fkey TO municipality_service_configs_service_id_fkey"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "customer_service_configs_customer_id_fkey TO municipality_service_configs_municipality_id_fkey"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "ck_customer_service_configs_non_negative_support_price "
        "TO ck_municipality_service_configs_non_negative_support_price"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "ck_customer_service_configs_non_negative_sale_price "
        "TO ck_municipality_service_configs_non_negative_sale_price"
    )
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "uq_customer_service_configs_customer_service TO uq_municipality_service_configs_municipality_service"
    )
    op.execute("ALTER TABLE customer_service_configs RENAME COLUMN customer_id TO municipality_id")
    op.execute("ALTER SEQUENCE customer_service_configs_id_seq RENAME TO municipality_service_configs_id_seq")
    op.execute(
        "ALTER TABLE customer_service_configs RENAME CONSTRAINT "
        "customer_service_configs_pkey TO municipality_service_configs_pkey"
    )
    op.rename_table("customer_service_configs", "municipality_service_configs")

    op.execute("ALTER TABLE users RENAME CONSTRAINT users_customer_id_fkey TO users_municipality_id_fkey")
    op.execute("ALTER TABLE users RENAME CONSTRAINT ck_users_role_customer TO ck_users_role_municipality")
    op.execute("ALTER TABLE users RENAME COLUMN customer_id TO municipality_id")

    op.execute("ALTER SEQUENCE customers_id_seq RENAME TO municipalities_id_seq")
    op.execute("ALTER TABLE customers RENAME CONSTRAINT customers_pkey TO municipalities_pkey")
    op.rename_table("customers", "municipalities")
