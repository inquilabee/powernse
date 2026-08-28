"""A resolved ``[start, end]`` date window over a staged archive."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from powernse.calendar import iter_trading_dates
from powernse.errors import ArchiveError


@dataclass(frozen=True, slots=True)
class DateWindow:
    """An inclusive trading-date range, already validated (``start <= end``)."""

    start: date
    end: date

    def __iter__(self) -> Iterator[date]:
        return iter_trading_dates(self.start, self.end)

    def calendar_days(self) -> Iterator[date]:
        """Every calendar day in the range, weekends and holidays included."""
        return iter_trading_dates(self.start, self.end, all_calendar_days=True)

    @classmethod
    def resolve(
        cls,
        from_date: date | None,
        to_date: date | None,
        *,
        latest: date | None,
        missing: str,
    ) -> "DateWindow":
        """Fill in the ends from ``latest`` when omitted; raise ``ArchiveError`` if that leaves it empty."""
        end = to_date or latest
        if end is None:
            raise ArchiveError(missing)
        start = from_date or end
        if start > end:
            msg = f"from_date {start} must be on or before to_date {end}"
            raise ValueError(msg)
        return cls(start, end)
