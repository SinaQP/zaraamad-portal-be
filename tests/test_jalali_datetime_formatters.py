from datetime import date, datetime

from app.common.formatters.jalali_datetime import (
    current_jalali_datetime_string,
    gregorian_date_to_jalali_date_string,
    gregorian_datetime_to_jalali_datetime_string,
    gregorian_datetime_to_time_string,
    jalali_date_parts_to_gregorian_date,
)


def test_gregorian_date_to_jalali_date_string_returns_expected_value() -> None:
    assert gregorian_date_to_jalali_date_string(date(2026, 3, 25)) == "1405-01-05"


def test_gregorian_datetime_to_jalali_datetime_string_preserves_time() -> None:
    assert (
        gregorian_datetime_to_jalali_datetime_string(datetime(2026, 3, 25, 14, 30, 45))
        == "1405-01-05 14:30:45"
    )


def test_gregorian_datetime_to_time_string_returns_expected_value() -> None:
    assert gregorian_datetime_to_time_string(datetime(2026, 3, 25, 14, 30, 45)) == "14:30:45"


def test_jalali_date_parts_to_gregorian_date_returns_expected_value() -> None:
    assert jalali_date_parts_to_gregorian_date(1405, 1, 5) == date(2026, 3, 25)


def test_current_jalali_datetime_string_uses_explicit_now() -> None:
    assert current_jalali_datetime_string(datetime(2026, 3, 25, 9, 8, 7)) == "1405-01-05 09:08:07"
