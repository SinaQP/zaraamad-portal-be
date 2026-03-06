"""initial schema

Revision ID: 20260306_0001
Revises:
Create Date: 2026-03-06 10:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260306_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_role_enum = sa.Enum("admin", "customer", name="user_role")
    otp_purpose_enum = sa.Enum("login", name="otp_purpose")
    user_role_enum.create(op.get_bind(), checkfirst=True)
    otp_purpose_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "municipalities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("province", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_municipalities_code"),
    )
    op.create_index(
        "ix_municipalities_code",
        "municipalities",
        ["code"],
        unique=True,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("mobile", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "municipality_id",
            sa.Integer(),
            sa.ForeignKey("municipalities.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "(role = 'admin' AND municipality_id IS NULL) OR "
            "(role = 'customer' AND municipality_id IS NOT NULL)",
            name="ck_users_role_municipality",
        ),
        sa.UniqueConstraint("mobile", name="uq_users_mobile"),
    )
    op.create_index("ix_users_mobile", "users", ["mobile"], unique=True)

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mobile", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("purpose", otp_purpose_enum, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_otp_codes_mobile", "otp_codes", ["mobile"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_otp_codes_mobile", table_name="otp_codes")
    op.drop_table("otp_codes")
    op.drop_index("ix_users_mobile", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_municipalities_code", table_name="municipalities")
    op.drop_table("municipalities")

    otp_purpose_enum = sa.Enum("login", name="otp_purpose")
    user_role_enum = sa.Enum("admin", "customer", name="user_role")
    otp_purpose_enum.drop(op.get_bind(), checkfirst=True)
    user_role_enum.drop(op.get_bind(), checkfirst=True)
