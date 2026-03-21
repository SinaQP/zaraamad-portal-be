"""add customer income datasets

Revision ID: 20260321_0021
Revises: 20260316_0020
Create Date: 2026-03-21 13:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260321_0021"
down_revision: str | None = "20260316_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_income_summaries",
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("registered_income_amount_12m", sa.BigInteger(), nullable=True),
        sa.Column("issued_bills_count_12m", sa.Integer(), nullable=True),
        sa.Column("paid_bills_count_12m", sa.Integer(), nullable=True),
        sa.Column("collection_rate_percent_12m", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("customer_id"),
    )

    op.create_table(
        "customer_income_buckets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("bucket_code", sa.String(length=50), nullable=False),
        sa.Column("chart_label", sa.String(length=255), nullable=True),
        sa.Column("registered_income_amount_12m", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id",
            "bucket_code",
            name="uq_customer_income_buckets_customer_bucket_code",
        ),
    )
    op.create_index(
        op.f("ix_customer_income_buckets_customer_id"),
        "customer_income_buckets",
        ["customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_customer_income_buckets_customer_id"),
        table_name="customer_income_buckets",
    )
    op.drop_table("customer_income_buckets")
    op.drop_table("customer_income_summaries")
