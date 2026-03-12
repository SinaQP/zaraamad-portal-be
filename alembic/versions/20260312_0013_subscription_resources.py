"""add subscription resources

Revision ID: 20260312_0013
Revises: 20260312_0012
Create Date: 2026-03-12 13:35:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260312_0013"
down_revision: str | None = "20260312_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("grace_period_end_date", sa.Date(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "subscription_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "expired",
                "grace",
                "near_expiry",
                name="subscription_message_status",
            ),
            nullable=False,
        ),
        sa.Column("message_template", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("status", name="uq_subscription_messages_status"),
    )


def downgrade() -> None:
    op.drop_table("subscription_messages")
    sa.Enum(
        "expired",
        "grace",
        "near_expiry",
        name="subscription_message_status",
    ).drop(op.get_bind(), checkfirst=True)
    op.drop_table("subscriptions")
