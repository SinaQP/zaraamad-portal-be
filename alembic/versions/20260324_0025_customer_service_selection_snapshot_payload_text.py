"""store customer service selection snapshot payload as text

Revision ID: 20260324_0025
Revises: 20260324_0024
Create Date: 2026-03-24 16:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260324_0025"
down_revision: str | None = "20260324_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "customer_service_selection_snapshots",
            "payload",
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            type_=sa.Text(),
            existing_nullable=False,
            postgresql_using="payload::text",
        )
        return

    with op.batch_alter_table("customer_service_selection_snapshots") as batch_op:
        batch_op.alter_column(
            "payload",
            existing_type=sa.JSON(),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "customer_service_selection_snapshots",
            "payload",
            existing_type=sa.Text(),
            type_=postgresql.JSONB(astext_type=sa.Text()),
            existing_nullable=False,
            postgresql_using="to_jsonb(payload)",
        )
        return

    with op.batch_alter_table("customer_service_selection_snapshots") as batch_op:
        batch_op.alter_column(
            "payload",
            existing_type=sa.Text(),
            type_=sa.JSON(),
            existing_nullable=False,
        )
