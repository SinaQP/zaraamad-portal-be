"""store encrypted customer database connection strings

Revision ID: 20260415_0032
Revises: 20260413_0031
Create Date: 2026-04-15 10:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260415_0032"
down_revision: str | None = "20260413_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customer_database_connections",
        sa.Column("encrypted_connection_string", sa.Text(), nullable=True),
    )
    op.add_column(
        "customer_database_connections",
        sa.Column("connection_string_hash", sa.String(length=64), nullable=True),
    )

    op.alter_column(
        "customer_database_connections",
        "host",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.alter_column(
        "customer_database_connections",
        "port",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "customer_database_connections",
        "database_name",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.alter_column(
        "customer_database_connections",
        "username",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.alter_column(
        "customer_database_connections",
        "secret_ref",
        existing_type=sa.String(length=500),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE customer_database_connections
        SET
            host = COALESCE(host, ''),
            port = COALESCE(port, 1433),
            database_name = COALESCE(database_name, ''),
            username = COALESCE(username, ''),
            secret_ref = COALESCE(secret_ref, '')
        """
    )

    op.alter_column(
        "customer_database_connections",
        "secret_ref",
        existing_type=sa.String(length=500),
        nullable=False,
    )
    op.alter_column(
        "customer_database_connections",
        "username",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "customer_database_connections",
        "database_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "customer_database_connections",
        "port",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "customer_database_connections",
        "host",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.drop_column("customer_database_connections", "connection_string_hash")
    op.drop_column("customer_database_connections", "encrypted_connection_string")
