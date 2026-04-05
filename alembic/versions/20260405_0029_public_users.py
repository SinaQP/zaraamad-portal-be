"""add public users and organization profile fields

Revision ID: 20260405_0029
Revises: 20260404_0028
Create Date: 2026-04-05 10:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260405_0029"
down_revision: str | None = "20260404_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'public'")
    op.add_column(
        "users",
        sa.Column("organization_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("organization_type", sa.String(length=100), nullable=True),
    )
    op.drop_constraint("ck_users_role_customer", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role_customer",
        "users",
        "("
        "role = 'admin' AND customer_id IS NULL AND "
        "organization_name IS NULL AND organization_type IS NULL"
        ") OR ("
        "role = 'customer' AND customer_id IS NOT NULL AND "
        "organization_name IS NULL AND organization_type IS NULL"
        ") OR ("
        "role = 'public' AND customer_id IS NULL AND "
        "organization_name IS NOT NULL AND organization_type IS NOT NULL"
        ")",
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE role::text = 'public'")
    op.drop_constraint("ck_users_role_customer", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role_customer",
        "users",
        "(role = 'admin' AND customer_id IS NULL) OR "
        "(role = 'customer' AND customer_id IS NOT NULL)",
    )
    op.drop_column("users", "organization_type")
    op.drop_column("users", "organization_name")
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'customer')")
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role
        USING role::text::user_role
        """
    )
    op.execute("DROP TYPE user_role_old")
