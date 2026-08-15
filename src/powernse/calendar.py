"""Indian equity trading calendar helpers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import exchange_calendars as xcals

INDIAN_EQUITY_CALENDAR = xcals.get_calendar("XBOM")


def is_weekend(trade_date: date) -> bool:
    """Return True for Saturday or Sunday."""
    return trade_date.weekday() >= 5


def iter_trading_dates(
    from_date: date,
    to_date: date,
    *,
    include_weekends: bool = False,
) -> Iterator[date]:
    """Yield trading sessions in range using the XBOM Indian equity calendar."""
    if from_date > to_date:
        msg = f"from_date {from_date} must be on or before to_date {to_date}"
        raise ValueError(msg)
    if include_weekends:
        current = from_date
        while current <= to_date:
            yield current
            current += timedelta(days=1)
        return
    sessions = INDIAN_EQUITY_CALENDAR.sessions_in_range(from_date, to_date)
    for session in sessions:
        yield session.date()
