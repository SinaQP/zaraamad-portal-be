from __future__ import annotations

import re
from datetime import date, datetime

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
    gregorian_year, gregorian_month, gregorian_day = _jalali_to_gregorian(year, month, day)
    return date(gregorian_year, gregorian_month, gregorian_day)


def jalali_datetime_string_to_gregorian_date(value: str) -> date:
    normalized_value = validate_jalali_datetime_string(value)
    return jalali_date_string_to_gregorian_date(normalized_value[:10])


def gregorian_date_to_jalali_date_string(value: date) -> str:
    year, month, day = _gregorian_to_jalali(value.year, value.month, value.day)
    return f"{year:04d}-{month:02d}-{day:02d}"


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
    gregorian_year, gregorian_month, gregorian_day = _jalali_to_gregorian(year, month, day)
    normalized_year, normalized_month, normalized_day = _gregorian_to_jalali(
        gregorian_year,
        gregorian_month,
        gregorian_day,
    )
    if (year, month, day) != (normalized_year, normalized_month, normalized_day):
        raise ValueError(error_message)
    return year, month, day


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
