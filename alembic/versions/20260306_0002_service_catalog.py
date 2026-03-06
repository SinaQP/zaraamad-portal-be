"""service catalog and municipality pricing config

Revision ID: 20260306_0002
Revises: 20260306_0001
Create Date: 2026-03-06 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260306_0002"
down_revision: str | None = "20260306_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "municipality_service_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("municipality_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("unit_price >= 0", name="ck_municipality_service_configs_non_negative_price"),
        sa.UniqueConstraint(
            "municipality_id",
            "service_id",
            name="uq_municipality_service_configs_municipality_service",
        ),
    )
    op.create_index(
        "ix_municipality_service_configs_municipality_id",
        "municipality_service_configs",
        ["municipality_id"],
        unique=False,
    )
    op.create_index(
        "ix_municipality_service_configs_service_id",
        "municipality_service_configs",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_municipality_service_configs_service_id", table_name="municipality_service_configs")
    op.drop_index("ix_municipality_service_configs_municipality_id", table_name="municipality_service_configs")
    op.drop_table("municipality_service_configs")

    op.drop_table("services")
