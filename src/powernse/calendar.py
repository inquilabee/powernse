"""Indian equity trading calendar helpers."""

from collections.abc import Iterator
from datetime import date, timedelta

import exchange_calendars as xcals

INDIAN_EQUITY_CALENDAR = xcals.get_calendar("XBOM")


def is_weekend(trade_date: date) -> bool:
    """Return True for Saturday or Sunday."""
    return trade_date.weekday() >= 5


def calendar_session_bounds() -> tuple[date, date]:
    """Return the first and last XBOM sessions known to ``exchange_calendars``."""
    first = INDIAN_EQUITY_CALENDAR.first_session.date()
    last = INDIAN_EQUITY_CALENDAR.last_session.date()
    return first, last


def _iter_weekdays(from_date: date, to_date: date) -> Iterator[date]:
    current = from_date
    while current <= to_date:
        if not is_weekend(current):
            yield current
        current += timedelta(days=1)


def iter_trading_dates(
    from_date: date,
    to_date: date,
    *,
    all_calendar_days: bool = False,
) -> Iterator[date]:
    """Yield dates in range.

    Default: XBOM trading sessions where the calendar covers the window.
    Outside XBOM coverage (currently before 2006-08-16), fall back to
    Monday–Friday so historical downloads still walk the range.
    When ``all_calendar_days`` is True: every calendar day (weekends and holidays included).
    """
    if from_date > to_date:
        msg = f"from_date {from_date} must be on or before to_date {to_date}"
        raise ValueError(msg)
    if all_calendar_days:
        current = from_date
        while current <= to_date:
            yield current
            current += timedelta(days=1)
        return

    first_session, last_session = calendar_session_bounds()

    if from_date < first_session:
        pre_end = min(to_date, first_session - timedelta(days=1))
        yield from _iter_weekdays(from_date, pre_end)

    range_start = max(from_date, first_session)
    range_end = min(to_date, last_session)
    if range_start <= range_end:
        sessions = INDIAN_EQUITY_CALENDAR.sessions_in_range(range_start, range_end)
        for session in sessions:
            yield session.date()

    if to_date > last_session:
        post_start = max(from_date, last_session + timedelta(days=1))
        yield from _iter_weekdays(post_start, to_date)
