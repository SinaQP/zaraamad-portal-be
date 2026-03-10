"""add service projects above service groups

Revision ID: 20260310_0007
Revises: 20260309_0006
Create Date: 2026-03-10 11:15:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260310_0007"
down_revision: str | None = "20260309_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.add_column("service_groups", sa.Column("project_id", sa.Integer(), nullable=True))

    op.execute(
        "INSERT INTO service_projects (code, name, description, sort_order, is_active, created_at, updated_at) "
        "VALUES ('general', 'General', 'Default project for existing service groups.', 0, true, now(), now())"
    )
    op.execute(
        "UPDATE service_groups "
        "SET project_id = (SELECT id FROM service_projects WHERE code = 'general' ORDER BY id LIMIT 1) "
        "WHERE project_id IS NULL"
    )

    op.alter_column("service_groups", "project_id", nullable=False)
    op.create_foreign_key(
        "fk_service_groups_project_id",
        "service_groups",
        "service_projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_service_groups_project_id", "service_groups", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_service_groups_project_id", table_name="service_groups")
    op.drop_constraint("fk_service_groups_project_id", "service_groups", type_="foreignkey")
    op.drop_column("service_groups", "project_id")
    op.drop_table("service_projects")
