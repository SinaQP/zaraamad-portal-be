"""add cached customer bridge status fields

Revision ID: 20260312_0012
Revises: 20260312_0011
Create Date: 2026-03-12 13:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260312_0012"
down_revision: str | None = "20260312_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customer_bridge_configs",
        sa.Column("last_online_status", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_bridge_configs",
        sa.Column("last_health_error", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer_bridge_configs", "last_health_error")
    op.drop_column("customer_bridge_configs", "last_health_checked_at")
    op.drop_column("customer_bridge_configs", "last_online_status")
