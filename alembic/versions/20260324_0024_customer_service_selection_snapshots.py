"""add customer service selection snapshots

Revision ID: 20260324_0024
Revises: 20260322_0023
Create Date: 2026-03-24 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260324_0024"
down_revision: str | None = "20260322_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_service_selection_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("selected_at", sa.String(length=19), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_customer_service_selection_snapshots_customer_id"),
        "customer_service_selection_snapshots",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_service_selection_snapshots_user_id"),
        "customer_service_selection_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_service_selection_snapshots_selected_at"),
        "customer_service_selection_snapshots",
        ["selected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_customer_service_selection_snapshots_selected_at"),
        table_name="customer_service_selection_snapshots",
    )
    op.drop_index(
        op.f("ix_customer_service_selection_snapshots_user_id"),
        table_name="customer_service_selection_snapshots",
    )
    op.drop_index(
        op.f("ix_customer_service_selection_snapshots_customer_id"),
        table_name="customer_service_selection_snapshots",
    )
    op.drop_table("customer_service_selection_snapshots")
