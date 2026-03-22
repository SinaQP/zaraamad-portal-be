"""add customer income monthly reports

Revision ID: 20260322_0023
Revises: 20260322_0022
Create Date: 2026-03-22 10:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260322_0023"
down_revision: str | None = "20260322_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_income_monthly_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("registered_income_amount", sa.BigInteger(), nullable=True),
        sa.Column("issued_bill_count", sa.Integer(), nullable=True),
        sa.Column("paid_bill_count", sa.Integer(), nullable=True),
        sa.Column("collection_rate_percent", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id",
            "month",
            name="uq_customer_income_monthly_reports_customer_month",
        ),
    )
    op.create_index(
        op.f("ix_customer_income_monthly_reports_customer_id"),
        "customer_income_monthly_reports",
        ["customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_customer_income_monthly_reports_customer_id"),
        table_name="customer_income_monthly_reports",
    )
    op.drop_table("customer_income_monthly_reports")
