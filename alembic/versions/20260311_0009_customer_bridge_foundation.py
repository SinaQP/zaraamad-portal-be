"""add customer bridge foundation fields

Revision ID: 20260311_0009
Revises: 20260311_0008
Create Date: 2026-03-11 16:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260311_0009"
down_revision: str | None = "20260311_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("bridge_base_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("bridge_api_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "bridge_is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("customers", "bridge_is_enabled")
    op.drop_column("customers", "bridge_api_key")
    op.drop_column("customers", "bridge_base_url")
