"""rename customer income columns

Revision ID: 20260322_0022
Revises: 20260321_0021
Create Date: 2026-03-22 00:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260322_0022"
down_revision: str | None = "20260321_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "customer_income_summaries",
        "registered_income_amount_12m",
        new_column_name="registered_income_amount",
    )
    op.alter_column(
        "customer_income_summaries",
        "issued_bills_count_12m",
        new_column_name="issued_bill_count",
    )
    op.alter_column(
        "customer_income_summaries",
        "paid_bills_count_12m",
        new_column_name="paid_bill_count",
    )
    op.alter_column(
        "customer_income_summaries",
        "collection_rate_percent_12m",
        new_column_name="collection_rate_percent",
    )
    op.alter_column(
        "customer_income_buckets",
        "chart_label",
        new_column_name="bucket_name",
    )
    op.alter_column(
        "customer_income_buckets",
        "registered_income_amount_12m",
        new_column_name="registered_income_amount",
    )


def downgrade() -> None:
    op.alter_column(
        "customer_income_buckets",
        "registered_income_amount",
        new_column_name="registered_income_amount_12m",
    )
    op.alter_column(
        "customer_income_buckets",
        "bucket_name",
        new_column_name="chart_label",
    )
    op.alter_column(
        "customer_income_summaries",
        "collection_rate_percent",
        new_column_name="collection_rate_percent_12m",
    )
    op.alter_column(
        "customer_income_summaries",
        "paid_bill_count",
        new_column_name="paid_bills_count_12m",
    )
    op.alter_column(
        "customer_income_summaries",
        "issued_bill_count",
        new_column_name="issued_bills_count_12m",
    )
    op.alter_column(
        "customer_income_summaries",
        "registered_income_amount",
        new_column_name="registered_income_amount_12m",
    )
