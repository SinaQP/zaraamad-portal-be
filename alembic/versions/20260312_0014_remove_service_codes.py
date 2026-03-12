"""remove service and service group codes

Revision ID: 20260312_0014
Revises: 20260312_0013
Create Date: 2026-03-12 13:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260312_0014"
down_revision: str | None = "20260312_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("services", "code")

    op.drop_column("service_groups", "code")


def downgrade() -> None:
    op.add_column("service_groups", sa.Column("code", sa.String(length=100), nullable=True))
    op.execute("UPDATE service_groups SET code = 'service-group-' || id::text WHERE code IS NULL")
    op.alter_column("service_groups", "code", nullable=False)

    op.add_column("services", sa.Column("code", sa.String(length=100), nullable=True))
    op.execute("UPDATE services SET code = 'service-' || id::text WHERE code IS NULL")
    op.alter_column("services", "code", nullable=False)
