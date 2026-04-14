"""add customer database connection metadata

Revision ID: 20260413_0031
Revises: 20260406_0030
Create Date: 2026-04-13 11:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260413_0031"
down_revision: str | None = "20260406_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_database_connections",
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("db_kind", sa.String(length=50), nullable=False, server_default="sqlserver"),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="1433"),
        sa.Column("database_name", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("secret_ref", sa.String(length=500), nullable=False),
        sa.Column("secret_version", sa.String(length=255), nullable=True),
        sa.Column("driver_name", sa.String(length=255), nullable=True),
        sa.Column("encrypt_connection", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("trust_server_certificate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("credential_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_connection_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_connection_test_success", sa.Boolean(), nullable=True),
        sa.Column("last_connection_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("customer_database_connections")
