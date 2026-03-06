"""add service groups and split municipality pricing

Revision ID: 20260306_0003
Revises: 20260306_0002
Create Date: 2026-03-06 14:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260306_0003"
down_revision: str | None = "20260306_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_service_groups_code"),
    )
    op.create_index("ix_service_groups_code", "service_groups", ["code"], unique=True)

    op.add_column("services", sa.Column("group_id", sa.Integer(), nullable=True))
    op.add_column("services", sa.Column("code", sa.String(length=100), nullable=True))

    op.execute(
        "INSERT INTO service_groups (code, name, description, sort_order, is_active, created_at, updated_at) "
        "VALUES ('general', 'General', 'Default group for existing services.', 0, true, now(), now())"
    )
    op.execute(
        "UPDATE services "
        "SET group_id = (SELECT id FROM service_groups WHERE code = 'general') "
        "WHERE group_id IS NULL"
    )
    op.execute("UPDATE services SET code = 'service-' || id::text WHERE code IS NULL")

    op.alter_column("services", "group_id", nullable=False)
    op.alter_column("services", "code", nullable=False)
    op.create_foreign_key(
        "fk_services_group_id",
        "services",
        "service_groups",
        ["group_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_services_code", "services", ["code"])
    op.create_index("ix_services_group_id", "services", ["group_id"], unique=False)
    op.create_index("ix_services_code", "services", ["code"], unique=True)

    op.add_column(
        "municipality_service_configs",
        sa.Column("sale_price", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "municipality_service_configs",
        sa.Column("support_price", sa.BigInteger(), nullable=True),
    )
    op.execute("UPDATE municipality_service_configs SET sale_price = unit_price WHERE sale_price IS NULL")
    op.drop_constraint(
        "ck_municipality_service_configs_non_negative_price",
        "municipality_service_configs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_municipality_service_configs_non_negative_sale_price",
        "municipality_service_configs",
        "sale_price >= 0",
    )
    op.create_check_constraint(
        "ck_municipality_service_configs_non_negative_support_price",
        "municipality_service_configs",
        "support_price IS NULL OR support_price >= 0",
    )
    op.alter_column("municipality_service_configs", "sale_price", nullable=False)
    op.drop_column("municipality_service_configs", "unit_price")


def downgrade() -> None:
    op.add_column(
        "municipality_service_configs",
        sa.Column("unit_price", sa.BigInteger(), nullable=True),
    )
    op.execute("UPDATE municipality_service_configs SET unit_price = sale_price WHERE unit_price IS NULL")
    op.drop_constraint(
        "ck_municipality_service_configs_non_negative_support_price",
        "municipality_service_configs",
        type_="check",
    )
    op.drop_constraint(
        "ck_municipality_service_configs_non_negative_sale_price",
        "municipality_service_configs",
        type_="check",
    )
    op.alter_column("municipality_service_configs", "unit_price", nullable=False)
    op.create_check_constraint(
        "ck_municipality_service_configs_non_negative_price",
        "municipality_service_configs",
        "unit_price >= 0",
    )
    op.drop_column("municipality_service_configs", "support_price")
    op.drop_column("municipality_service_configs", "sale_price")

    op.drop_index("ix_services_code", table_name="services")
    op.drop_index("ix_services_group_id", table_name="services")
    op.drop_constraint("uq_services_code", "services", type_="unique")
    op.drop_constraint("fk_services_group_id", "services", type_="foreignkey")
    op.drop_column("services", "code")
    op.drop_column("services", "group_id")

    op.drop_index("ix_service_groups_code", table_name="service_groups")
    op.drop_table("service_groups")
