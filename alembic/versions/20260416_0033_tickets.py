"""add tickets table

Revision ID: 20260416_0033
Revises: 20260415_0032
Create Date: 2026-04-16 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260416_0033"
down_revision: str | None = "20260415_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ticket_status_enum = postgresql.ENUM(
        "open",
        "in_progress",
        "resolved",
        "closed",
        "rejected",
        name="ticket_status",
        create_type=True,
    )
    ticket_priority_enum = postgresql.ENUM(
        "low",
        "medium",
        "high",
        "urgent",
        name="ticket_priority",
        create_type=True,
    )
    ticket_status_enum.create(op.get_bind(), checkfirst=True)
    ticket_priority_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open",
                "in_progress",
                "resolved",
                "closed",
                "rejected",
                name="ticket_status",
                create_type=False,
            ),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "urgent",
                name="ticket_priority",
                create_type=False,
            ),
            server_default="medium",
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("status_changed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["status_changed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tickets_status"), "tickets", ["status"], unique=False)
    op.create_index(op.f("ix_tickets_priority"), "tickets", ["priority"], unique=False)
    op.create_index(op.f("ix_tickets_created_by_user_id"), "tickets", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_tickets_assigned_to_user_id"), "tickets", ["assigned_to_user_id"], unique=False)
    op.create_index(op.f("ix_tickets_is_active"), "tickets", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tickets_is_active"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_assigned_to_user_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_created_by_user_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_priority"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_status"), table_name="tickets")
    op.drop_table("tickets")

    ticket_priority_enum = postgresql.ENUM(
        "low",
        "medium",
        "high",
        "urgent",
        name="ticket_priority",
        create_type=True,
    )
    ticket_status_enum = postgresql.ENUM(
        "open",
        "in_progress",
        "resolved",
        "closed",
        "rejected",
        name="ticket_status",
        create_type=True,
    )
    ticket_priority_enum.drop(op.get_bind(), checkfirst=True)
    ticket_status_enum.drop(op.get_bind(), checkfirst=True)

