"""add customer manager name

Revision ID: 20260315_0019
Revises: 20260315_0018
Create Date: 2026-03-15 15:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260315_0019"
down_revision: str | None = "20260315_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("manager_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "manager_name")
