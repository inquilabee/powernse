"""Indian equity (XBOM) trading-day calendar."""

from collections.abc import Iterator
from datetime import date, timedelta

import exchange_calendars as xcals


class TradingCalendar:
    """XBOM sessions, with a Monday-Friday fallback outside the calendar's coverage.

    ``exchange_calendars`` only covers XBOM from 2006-08-16 onward; for ranges
    before (or after) that window this walks weekdays so historical downloads
    still make progress instead of raising.
    """

    def __init__(self, name: str = "XBOM") -> None:
        self.name = name
        self._calendar = xcals.get_calendar(name)

    @staticmethod
    def is_weekend(day: date) -> bool:
        """True for Saturday or Sunday."""
        return day.weekday() >= 5

    def session_bounds(self) -> tuple[date, date]:
        """First and last sessions ``exchange_calendars`` knows for this calendar."""
        return self._calendar.first_session.date(), self._calendar.last_session.date()

    def iter_dates(self, from_date: date, to_date: date, *, all_calendar_days: bool = False) -> Iterator[date]:
        """Yield dates in ``[from_date, to_date]``.

        Default: XBOM trading sessions where the calendar covers the window, and
        Monday-Friday outside it. ``all_calendar_days=True`` yields every calendar
        day (weekends and holidays included).
        """
        if from_date > to_date:
            msg = f"from_date {from_date} must be on or before to_date {to_date}"
            raise ValueError(msg)

        if all_calendar_days:
            yield from self._every_day(from_date, to_date)
            return

        first_session, last_session = self.session_bounds()

        if from_date < first_session:
            yield from self._weekdays(from_date, min(to_date, first_session - timedelta(days=1)))

        range_start = max(from_date, first_session)
        range_end = min(to_date, last_session)
        if range_start <= range_end:
            for session in self._calendar.sessions_in_range(range_start, range_end):
                yield session.date()

        if to_date > last_session:
            yield from self._weekdays(max(from_date, last_session + timedelta(days=1)), to_date)

    # -- arithmetic ----------------------------------------------------------

    def sessions(self, from_date: date, to_date: date) -> list[date]:
        """Trading days in the inclusive range, as a list."""
        return list(self.iter_dates(from_date, to_date))

    def count(self, from_date: date, to_date: date) -> int:
        """Number of trading days in ``[from_date, to_date]``."""
        return len(self.sessions(from_date, to_date))

    def offset(self, day: date, n: int) -> date:
        """The session ``n`` steps from ``day``.

        ``n > 0`` -> the ``n``-th session strictly after ``day``; ``n < 0`` -> the
        ``|n|``-th strictly before; ``n == 0`` -> ``day`` unchanged. Outside the
        calendar's coverage this counts Monday-Friday, matching ``iter_dates``.
        """
        if n == 0:
            return day
        span = abs(n)
        pad = timedelta(days=span * 3 + 10)  # >= span sessions even across long weekends + holidays
        window = (day + timedelta(days=1), day + pad) if n > 0 else (day - pad, day - timedelta(days=1))
        sessions = self.sessions(*window)
        if len(sessions) < span:
            msg = f"offset({day}, {n}) needs a wider window than {pad.days} calendar days"
            raise ValueError(msg)
        return sessions[span - 1] if n > 0 else sessions[-span]

    def _weekdays(self, from_date: date, to_date: date) -> Iterator[date]:
        for day in self._every_day(from_date, to_date):
            if not self.is_weekend(day):
                yield day

    @staticmethod
    def _every_day(from_date: date, to_date: date) -> Iterator[date]:
        current = from_date
        while current <= to_date:
            yield current
            current += timedelta(days=1)


XBOM = TradingCalendar("XBOM")


def iter_trading_dates(from_date: date, to_date: date, *, all_calendar_days: bool = False) -> Iterator[date]:
    """XBOM trading sessions in ``[from_date, to_date]`` (weekday fallback outside coverage)."""
    return XBOM.iter_dates(from_date, to_date, all_calendar_days=all_calendar_days)
