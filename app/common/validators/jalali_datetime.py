from __future__ import annotations

import re
from datetime import date

from app.common.formatters.jalali_datetime import (
    current_jalali_datetime_string,
    gregorian_date_to_jalali_date_parts,
    gregorian_date_to_jalali_date_string,
    jalali_date_parts_to_gregorian_date,
)

__all__ = [
    "current_jalali_datetime_string",
    "gregorian_date_to_jalali_date_string",
    "jalali_date_string_to_gregorian_date",
    "jalali_datetime_string_to_gregorian_date",
    "validate_jalali_date_string",
    "validate_jalali_datetime_string",
]

_JALALI_DATE_ERROR = "Invalid Jalali date format. Use YYYY-MM-DD."
_JALALI_DATETIME_ERROR = "Invalid Jalali datetime format. Use YYYY-MM-DD HH:MM:SS."
_JALALI_DATE_PATTERN = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")
_JALALI_DATETIME_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
    r"[ T]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?:\.\d+)?"
    r"(?P<timezone>Z|[+-]\d{2}:?\d{2})?$"
)


def validate_jalali_date_string(value: str) -> str:
    normalized_value = value.strip()
    year, month, day = _parse_jalali_date_parts(normalized_value, error_message=_JALALI_DATE_ERROR)
    return f"{year:04d}-{month:02d}-{day:02d}"


def validate_jalali_datetime_string(value: str) -> str:
    normalized_value = value.strip()
    match = _JALALI_DATETIME_PATTERN.fullmatch(normalized_value)
    if match is None:
        raise ValueError(_JALALI_DATETIME_ERROR)
    parsed_parts = match.groupdict()
    year, month, day = _parse_jalali_date_parts(
        f"{parsed_parts['year']}-{parsed_parts['month']}-{parsed_parts['day']}",
        error_message=_JALALI_DATETIME_ERROR,
    )
    hour = int(parsed_parts["hour"])
    minute = int(parsed_parts["minute"])
    second = int(parsed_parts["second"])
    if not 0 <= hour <= 23:
        raise ValueError(_JALALI_DATETIME_ERROR)
    if not 0 <= minute <= 59:
        raise ValueError(_JALALI_DATETIME_ERROR)
    if not 0 <= second <= 59:
        raise ValueError(_JALALI_DATETIME_ERROR)
    return (
        f"{year:04d}-{month:02d}-{day:02d} "
        f"{hour:02d}:{minute:02d}:{second:02d}"
    )


def jalali_date_string_to_gregorian_date(value: str) -> date:
    normalized_value = validate_jalali_date_string(value)
    year, month, day = _parse_jalali_date_parts(normalized_value, error_message=_JALALI_DATE_ERROR)
    return jalali_date_parts_to_gregorian_date(year, month, day)


def jalali_datetime_string_to_gregorian_date(value: str) -> date:
    normalized_value = validate_jalali_datetime_string(value)
    return jalali_date_string_to_gregorian_date(normalized_value[:10])

def _parse_jalali_date_parts(value: str, *, error_message: str) -> tuple[int, int, int]:
    match = _JALALI_DATE_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(error_message)
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    if not 1 <= month <= 12:
        raise ValueError(error_message)
    if not 1 <= day <= 31:
        raise ValueError(error_message)
    gregorian_date = jalali_date_parts_to_gregorian_date(year, month, day)
    normalized_year, normalized_month, normalized_day = gregorian_date_to_jalali_date_parts(
        gregorian_date,
    )
    if (year, month, day) != (normalized_year, normalized_month, normalized_day):
        raise ValueError(error_message)
    return year, month, day
