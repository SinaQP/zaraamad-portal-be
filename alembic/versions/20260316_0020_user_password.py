"""add customer manager name

Revision ID: 20260316_0020
Revises: 20260315_0019
Create Date: 2026-03-16 11:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260316_0020"
down_revision: str | None = "20260315_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password")
