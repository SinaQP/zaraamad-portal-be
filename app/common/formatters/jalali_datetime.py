from __future__ import annotations

from datetime import date, datetime


def jalali_date_parts_to_gregorian_date(year: int, month: int, day: int) -> date:
    gregorian_year, gregorian_month, gregorian_day = _jalali_to_gregorian(year, month, day)
    return date(gregorian_year, gregorian_month, gregorian_day)


def gregorian_date_to_jalali_date_parts(value: date) -> tuple[int, int, int]:
    return _gregorian_to_jalali(value.year, value.month, value.day)


def gregorian_date_to_jalali_date_string(value: date) -> str:
    year, month, day = gregorian_date_to_jalali_date_parts(value)
    return f"{year:04d}-{month:02d}-{day:02d}"


def gregorian_datetime_to_jalali_datetime_string(value: datetime) -> str:
    return (
        f"{gregorian_date_to_jalali_date_string(value.date())} "
        f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
    )


def gregorian_datetime_to_time_string(value: datetime) -> str:
    return f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"


def current_jalali_datetime_string(now: datetime | None = None) -> str:
    current_datetime = now or datetime.now()
    return gregorian_datetime_to_jalali_datetime_string(current_datetime)


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
