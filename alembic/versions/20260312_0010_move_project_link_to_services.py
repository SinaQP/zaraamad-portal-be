"""move project ownership from groups to services

Revision ID: 20260312_0010
Revises: 20260311_0009
Create Date: 2026-03-12 10:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260312_0010"
down_revision: str | None = "20260311_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("services", sa.Column("project_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE services AS s
        SET project_id = sg.project_id
        FROM service_groups AS sg
        WHERE s.group_id = sg.id
          AND s.project_id IS NULL
        """
    )

    op.alter_column("services", "project_id", nullable=False)
    op.create_foreign_key(
        "fk_services_project_id",
        "services",
        "service_projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_services_project_id", "services", ["project_id"], unique=False)

    op.drop_index("ix_service_groups_project_id", table_name="service_groups")
    op.drop_constraint("fk_service_groups_project_id", "service_groups", type_="foreignkey")
    op.drop_column("service_groups", "project_id")


def downgrade() -> None:
    op.add_column("service_groups", sa.Column("project_id", sa.Integer(), nullable=True))

    op.execute(
        """
        INSERT INTO service_projects (name, description, sort_order, is_active, created_at, updated_at)
        SELECT
            'General',
            'Fallback project for downgraded service groups.',
            0,
            true,
            now(),
            now()
        WHERE NOT EXISTS (SELECT 1 FROM service_projects)
        """
    )

    op.execute(
        """
        UPDATE service_groups AS sg
        SET project_id = COALESCE(
            (
                SELECT MIN(s.project_id)
                FROM services AS s
                WHERE s.group_id = sg.id
            ),
            (
                SELECT id
                FROM service_projects
                ORDER BY id
                LIMIT 1
            )
        )
        WHERE sg.project_id IS NULL
        """
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

    op.drop_index("ix_services_project_id", table_name="services")
    op.drop_constraint("fk_services_project_id", "services", type_="foreignkey")
    op.drop_column("services", "project_id")
