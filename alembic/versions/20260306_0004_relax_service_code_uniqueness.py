"""relax service and service-group code uniqueness

Revision ID: 20260306_0004
Revises: 20260306_0003
Create Date: 2026-03-06 14:45:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260306_0004"
down_revision: str | None = "20260306_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_services_code", table_name="services")
    op.drop_constraint("uq_services_code", "services", type_="unique")
    op.drop_index("ix_service_groups_code", table_name="service_groups")
    op.drop_constraint("uq_service_groups_code", "service_groups", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("uq_service_groups_code", "service_groups", ["code"])
    op.create_index("ix_service_groups_code", "service_groups", ["code"], unique=True)
    op.create_unique_constraint("uq_services_code", "services", ["code"])
    op.create_index("ix_services_code", "services", ["code"], unique=True)
