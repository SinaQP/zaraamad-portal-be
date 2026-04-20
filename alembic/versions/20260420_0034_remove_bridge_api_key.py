"""remove bridge api key column

Revision ID: 20260420_0034
Revises: 20260416_0033
Create Date: 2026-04-20 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260420_0034"
down_revision: str | None = "20260416_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("customer_bridge_configs", "bridge_api_key")


def downgrade() -> None:
    op.add_column(
        "customer_bridge_configs",
        sa.Column("bridge_api_key", sa.String(length=255), nullable=True),
    )
