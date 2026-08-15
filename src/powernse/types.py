"""Small shared value types."""

from dataclasses import dataclass
from datetime import date
from typing import Self


@dataclass(frozen=True, slots=True)
class DownloadSummary:
    """Counts from a download run."""

    downloaded_count: int
    skipped_existing_count: int
    failed_count: int = 0

    @property
    def total_considered(self) -> int:
        return self.downloaded_count + self.skipped_existing_count + self.failed_count

    def __add__(self, other: Self) -> Self:
        if not isinstance(other, DownloadSummary):
            return NotImplemented
        return type(self)(
            downloaded_count=self.downloaded_count + other.downloaded_count,
            skipped_existing_count=self.skipped_existing_count + other.skipped_existing_count,
            failed_count=self.failed_count + other.failed_count,
        )


@dataclass(frozen=True, slots=True)
class OhlcBar:
    """One symbol's end-of-day OHLC from a staged bhavcopy row."""

    trade_date: date
    symbol: str
    series: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    isin: str | None = None


@dataclass(frozen=True, slots=True)
class AdjustedOhlcBar:
    """Equity OHLC with an opt-in cumulative adjustment factor applied."""

    trade_date: date
    symbol: str
    series: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    factor: float
    isin: str | None = None


@dataclass(frozen=True, slots=True)
class FoBar:
    """One F&O instrument row from a staged F&O bhavcopy."""

    trade_date: date
    symbol: str
    instrument_type: str
    expiry: date | None
    strike: float | None
    option_type: str | None
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int | None = None


@dataclass(frozen=True, slots=True)
class IndexBar:
    """One index OHLC row from a staged index-closes file."""

    trade_date: date
    index_name: str
    open: float
    high: float
    low: float
    close: float
