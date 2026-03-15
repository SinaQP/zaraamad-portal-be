from __future__ import annotations

import re
from datetime import datetime

_JALALI_DATETIME_ERROR = "Invalid Jalali datetime format. Use YYYY-MM-DD HH:MM:SS."
_JALALI_DATETIME_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
    r"[ T]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?:\.\d+)?"
    r"(?P<timezone>Z|[+-]\d{2}:?\d{2})?$"
)


def validate_jalali_datetime_string(value: str) -> str:
    normalized_value = value.strip()
    match = _JALALI_DATETIME_PATTERN.fullmatch(normalized_value)
    if match is None:
        raise ValueError(_JALALI_DATETIME_ERROR)
    parsed_parts = {
        name: int(raw_value)
        for name, raw_value in match.groupdict().items()
        if name != "timezone"
    }
    if not 1 <= parsed_parts["month"] <= 12:
        raise ValueError(_JALALI_DATETIME_ERROR)
    if not 1 <= parsed_parts["day"] <= 31:
        raise ValueError(_JALALI_DATETIME_ERROR)
    if not 0 <= parsed_parts["hour"] <= 23:
        raise ValueError(_JALALI_DATETIME_ERROR)
    if not 0 <= parsed_parts["minute"] <= 59:
        raise ValueError(_JALALI_DATETIME_ERROR)
    if not 0 <= parsed_parts["second"] <= 59:
        raise ValueError(_JALALI_DATETIME_ERROR)
    return (
        f"{parsed_parts['year']:04d}-{parsed_parts['month']:02d}-{parsed_parts['day']:02d} "
        f"{parsed_parts['hour']:02d}:{parsed_parts['minute']:02d}:{parsed_parts['second']:02d}"
    )


def current_jalali_datetime_string(now: datetime | None = None) -> str:
    current_datetime = now or datetime.now()
    year, month, day = _gregorian_to_jalali(
        current_datetime.year,
        current_datetime.month,
        current_datetime.day,
    )
    return (
        f"{year:04d}-{month:02d}-{day:02d} "
        f"{current_datetime.hour:02d}:{current_datetime.minute:02d}:{current_datetime.second:02d}"
    )


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
