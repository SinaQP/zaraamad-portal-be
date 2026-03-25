"""store customer service selection snapshot selected_at as datetime

Revision ID: 20260325_0027
Revises: 20260324_0026
Create Date: 2026-03-25 09:30:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time

from alembic import op
import sqlalchemy as sa

revision: str = "20260325_0027"
down_revision: str | None = "20260324_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "customer_service_selection_snapshots"


def upgrade() -> None:
    upgrade_snapshot_table = sa.table(
        _TABLE_NAME,
        sa.column("id", sa.Integer()),
        sa.column("selected_at", sa.Date()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("selected_at_tmp", sa.DateTime(timezone=True)),
    )

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.add_column(sa.Column("selected_at_tmp", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            upgrade_snapshot_table.c.id,
            upgrade_snapshot_table.c.selected_at,
            upgrade_snapshot_table.c.created_at,
        )
    ).mappings()
    for row in rows:
        bind.execute(
            upgrade_snapshot_table.update()
            .where(upgrade_snapshot_table.c.id == row["id"])
            .values(
                selected_at_tmp=_combine_selected_date_with_created_time(
                    selected_at=row["selected_at"],
                    created_at=row["created_at"],
                )
            )
        )

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.drop_index(op.f("ix_customer_service_selection_snapshots_selected_at"))
        batch_op.drop_column("selected_at")
        batch_op.alter_column(
            "selected_at_tmp",
            new_column_name="selected_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_index(
            op.f("ix_customer_service_selection_snapshots_selected_at"),
            ["selected_at"],
            unique=False,
        )


def downgrade() -> None:
    downgrade_snapshot_table = sa.table(
        _TABLE_NAME,
        sa.column("id", sa.Integer()),
        sa.column("selected_at", sa.DateTime(timezone=True)),
        sa.column("selected_at_tmp", sa.Date()),
    )

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.add_column(sa.Column("selected_at_tmp", sa.Date(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            downgrade_snapshot_table.c.id,
            downgrade_snapshot_table.c.selected_at,
        )
    ).mappings()
    for row in rows:
        bind.execute(
            downgrade_snapshot_table.update()
            .where(downgrade_snapshot_table.c.id == row["id"])
            .values(selected_at_tmp=_selected_datetime_to_date(row["selected_at"]))
        )

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.drop_index(op.f("ix_customer_service_selection_snapshots_selected_at"))
        batch_op.drop_column("selected_at")
        batch_op.alter_column(
            "selected_at_tmp",
            new_column_name="selected_at",
            existing_type=sa.Date(),
            nullable=False,
        )
        batch_op.create_index(
            op.f("ix_customer_service_selection_snapshots_selected_at"),
            ["selected_at"],
            unique=False,
        )


def _combine_selected_date_with_created_time(
    *,
    selected_at: date,
    created_at: datetime | None,
) -> datetime:
    if created_at is None:
        return datetime.combine(selected_at, time.min)
    snapshot_time = created_at.timetz() if created_at.tzinfo is not None else created_at.time()
    return datetime.combine(selected_at, snapshot_time)


def _selected_datetime_to_date(value: datetime) -> date:
    return value.date()
