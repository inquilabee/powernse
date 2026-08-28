"""TradingCalendar arithmetic."""

from datetime import date

import pytest

from powernse.calendar import XBOM, iter_trading_dates


def test_sessions_matches_iter_trading_dates() -> None:
    lo, hi = date(2024, 8, 1), date(2024, 8, 31)
    assert XBOM.sessions(lo, hi) == list(iter_trading_dates(lo, hi))


def test_count_over_a_known_week() -> None:
    # Mon 2024-08-05 .. Sun 2024-08-11: 5 weekdays, no NSE holiday that week.
    assert XBOM.count(date(2024, 8, 5), date(2024, 8, 11)) == 5


def test_offset_next_and_previous_session() -> None:
    fri = date(2024, 8, 9)
    mon = date(2024, 8, 12)
    assert XBOM.offset(fri, 1) == mon  # skips the weekend
    assert XBOM.offset(mon, -1) == fri
    assert XBOM.offset(fri, 0) == fri


def test_offset_round_trips() -> None:
    d = date(2024, 3, 15)
    for k in (1, 7, 30, 128):
        assert XBOM.offset(XBOM.offset(d, k), -k) == d


def test_offset_crosses_holiday() -> None:
    # 2024-08-15 is Independence Day (NSE closed); 14th -> 16th.
    assert XBOM.offset(date(2024, 8, 14), 1) == date(2024, 8, 16)


def test_offset_pre_xbom_coverage_uses_weekdays() -> None:
    # exchange_calendars covers XBOM from 2006-08-16; earlier -> weekday fallback.
    assert XBOM.offset(date(2000, 1, 7), 1) == date(2000, 1, 10)  # Fri -> Mon


def test_offset_rejects_from_before_to() -> None:
    with pytest.raises(ValueError, match="on or before"):
        XBOM.sessions(date(2024, 8, 10), date(2024, 8, 1))


def test_is_session() -> None:
    assert XBOM.is_session(date(2024, 8, 9)) is True  # Friday, trading day
    assert XBOM.is_session(date(2024, 8, 10)) is False  # Saturday
    assert XBOM.is_session(date(2024, 8, 15)) is False  # Independence Day, NSE closed


def test_holidays_over_a_month() -> None:
    got = XBOM.holidays(date(2024, 8, 1), date(2024, 8, 31))
    assert date(2024, 8, 15) in got  # Independence Day
    assert all(day.weekday() < 5 for day in got)  # weekdays only, weekends excluded
    assert date(2024, 8, 9) not in got  # a normal trading day
