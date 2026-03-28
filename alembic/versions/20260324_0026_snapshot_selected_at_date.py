"""store customer service selection snapshot selected_at as date

Revision ID: 20260324_0026
Revises: 20260324_0025
Create Date: 2026-03-24 18:10:00
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date

from alembic import op
import sqlalchemy as sa

revision: str = "20260324_0026"
down_revision: str | None = "20260324_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JALALI_DATETIME_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
    r"[ T]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})$"
)

snapshot_table = sa.table(
    "customer_service_selection_snapshots",
    sa.column("id", sa.Integer()),
    sa.column("selected_at", sa.String(length=19)),
    sa.column("selected_at_tmp", sa.Date()),
)


def upgrade() -> None:
    with op.batch_alter_table("customer_service_selection_snapshots") as batch_op:
        batch_op.add_column(sa.Column("selected_at_tmp", sa.Date(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            snapshot_table.c.id,
            snapshot_table.c.selected_at,
        )
    ).mappings()
    for row in rows:
        bind.execute(
            snapshot_table.update()
            .where(snapshot_table.c.id == row["id"])
            .values(selected_at_tmp=_jalali_datetime_string_to_gregorian_date(row["selected_at"]))
        )

    with op.batch_alter_table("customer_service_selection_snapshots") as batch_op:
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


def downgrade() -> None:
    with op.batch_alter_table("customer_service_selection_snapshots") as batch_op:
        batch_op.add_column(sa.Column("selected_at_tmp", sa.String(length=19), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            snapshot_table.c.id,
            snapshot_table.c.selected_at,
        )
    ).mappings()
    for row in rows:
        bind.execute(
            snapshot_table.update()
            .where(snapshot_table.c.id == row["id"])
            .values(selected_at_tmp=_gregorian_date_to_jalali_datetime_string(row["selected_at"]))
        )

    with op.batch_alter_table("customer_service_selection_snapshots") as batch_op:
        batch_op.drop_index(op.f("ix_customer_service_selection_snapshots_selected_at"))
        batch_op.drop_column("selected_at")
        batch_op.alter_column(
            "selected_at_tmp",
            new_column_name="selected_at",
            existing_type=sa.String(length=19),
            nullable=False,
        )
        batch_op.create_index(
            op.f("ix_customer_service_selection_snapshots_selected_at"),
            ["selected_at"],
            unique=False,
        )


def _jalali_datetime_string_to_gregorian_date(value: str) -> date:
    match = _JALALI_DATETIME_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported selected_at value: {value!r}")
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    gregorian_year, gregorian_month, gregorian_day = _jalali_to_gregorian(year, month, day)
    return date(gregorian_year, gregorian_month, gregorian_day)


def _gregorian_date_to_jalali_datetime_string(value: date) -> str:
    year, month, day = _gregorian_to_jalali(value.year, value.month, value.day)
    return f"{year:04d}-{month:02d}-{day:02d} 00:00:00"


def _gregorian_to_jalali(year: int, month: int, day: int) -> tuple[int, int, int]:
    gregorian_day_offsets = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if year > 1600:
        jalali_year = 979
        year -= 1600
    else:
        jalali_year = 0
        year -= 621
    leap_adjusted_year = year + 1 if month > 2 else year
    days = (
        365 * year
        + (leap_adjusted_year + 3) // 4
        - (leap_adjusted_year + 99) // 100
        + (leap_adjusted_year + 399) // 400
        - 80
        + day
        + gregorian_day_offsets[month - 1]
    )
    jalali_year += 33 * (days // 12053)
    days %= 12053
    jalali_year += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jalali_year += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jalali_month = 1 + days // 31
        jalali_day = 1 + days % 31
    else:
        jalali_month = 7 + (days - 186) // 30
        jalali_day = 1 + (days - 186) % 30
    return jalali_year, jalali_month, jalali_day


def _jalali_to_gregorian(year: int, month: int, day: int) -> tuple[int, int, int]:
    year += 1595
    days = (
        -355668
        + 365 * year
        + (year // 33) * 8
        + ((year % 33) + 3) // 4
        + day
    )
    if month <= 6:
        days += (month - 1) * 31
    else:
        days += (month - 7) * 30 + 186
    gregorian_year = 400 * (days // 146097)
    days %= 146097
    leap_year = True
    if days >= 36525:
        days -= 1
        gregorian_year += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
        else:
            leap_year = False
    gregorian_year += 4 * (days // 1461)
    days %= 1461
    if days >= 366:
        leap_year = False
        days -= 1
        gregorian_year += days // 365
        days %= 365
    gregorian_day = days + 1
    gregorian_month_lengths = [
        0,
        31,
        29 if leap_year else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    gregorian_month = 1
    while gregorian_month <= 12 and gregorian_day > gregorian_month_lengths[gregorian_month]:
        gregorian_day -= gregorian_month_lengths[gregorian_month]
        gregorian_month += 1
    return gregorian_year, gregorian_month, gregorian_day
