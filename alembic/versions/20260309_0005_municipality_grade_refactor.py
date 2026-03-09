"""replace municipality code/province/city with grade

Revision ID: 20260309_0005
Revises: 20260306_0004
Create Date: 2026-03-09 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260309_0005"
down_revision: str | None = "20260306_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_municipalities_code", table_name="municipalities")
    op.drop_constraint("uq_municipalities_code", "municipalities", type_="unique")
    op.drop_column("municipalities", "code")
    op.drop_column("municipalities", "province")
    op.drop_column("municipalities", "city")
    op.add_column(
        "municipalities",
        sa.Column("grade", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.alter_column("municipalities", "grade", server_default=None)


def downgrade() -> None:
    op.drop_column("municipalities", "grade")
    op.add_column("municipalities", sa.Column("city", sa.String(length=255), nullable=True))
    op.add_column("municipalities", sa.Column("province", sa.String(length=255), nullable=True))
    op.add_column("municipalities", sa.Column("code", sa.String(length=100), nullable=True))
    op.execute("UPDATE municipalities SET code = 'M-' || id::text WHERE code IS NULL")
    op.alter_column("municipalities", "code", nullable=False)
    op.create_unique_constraint("uq_municipalities_code", "municipalities", ["code"])
    op.create_index("ix_municipalities_code", "municipalities", ["code"], unique=True)
