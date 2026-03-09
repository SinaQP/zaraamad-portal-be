"""remove email field from users

Revision ID: 20260309_0006
Revises: 20260309_0005
Create Date: 2026-03-09 12:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260309_0006"
down_revision: str | None = "20260309_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("users", "email")


def downgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
