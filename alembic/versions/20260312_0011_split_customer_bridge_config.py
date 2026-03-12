"""split customer bridge config into separate table

Revision ID: 20260312_0011
Revises: 20260312_0010
Create Date: 2026-03-12 12:15:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260312_0011"
down_revision: str | None = "20260312_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_bridge_configs",
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("bridge_base_url", sa.String(length=500), nullable=True),
        sa.Column("bridge_api_key", sa.String(length=255), nullable=True),
        sa.Column(
            "bridge_is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.execute(
        """
        INSERT INTO customer_bridge_configs (
            customer_id,
            bridge_base_url,
            bridge_api_key,
            bridge_is_enabled,
            created_at,
            updated_at
        )
        SELECT
            id,
            bridge_base_url,
            bridge_api_key,
            bridge_is_enabled,
            created_at,
            updated_at
        FROM customers
        WHERE bridge_base_url IS NOT NULL
           OR bridge_api_key IS NOT NULL
           OR bridge_is_enabled = true
        """
    )

    op.drop_column("customers", "bridge_is_enabled")
    op.drop_column("customers", "bridge_api_key")
    op.drop_column("customers", "bridge_base_url")


def downgrade() -> None:
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

    op.execute(
        """
        UPDATE customers AS c
        SET
            bridge_base_url = cbc.bridge_base_url,
            bridge_api_key = cbc.bridge_api_key,
            bridge_is_enabled = cbc.bridge_is_enabled
        FROM customer_bridge_configs AS cbc
        WHERE c.id = cbc.customer_id
        """
    )

    op.drop_table("customer_bridge_configs")
