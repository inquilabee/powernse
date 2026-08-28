"""Read equity OHLC out of staged CM bhavcopy days."""

from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from typing import ClassVar

import pandas as pd

from powernse.datasets import BHAVCOPY
from powernse.errors import ArchiveError
from powernse.parsers.rows import BHAVCOPY_ROWS, OhlcRow
from powernse.reading.base import DatedFrameReader
from powernse.schemas import OHLC_SCHEMA


class BhavcopyReader(DatedFrameReader[OhlcRow]):
    """OHLC bars for a symbol / a day / the latest day, and the Date x Symbol matrix."""

    dataset = BHAVCOPY
    schema = OHLC_SCHEMA
    parser = BHAVCOPY_ROWS
    label = "bhavcopy"

    # Literal-keyed getters keep wide_frame()'s dynamic `column` type-safe --
    # an OhlcRow TypedDict can't be subscripted with a non-literal key.
    _COLUMN_GETTERS: ClassVar[dict[str, Callable[[OhlcRow], float]]] = {
        "open": lambda row: row["open"],
        "high": lambda row: row["high"],
        "low": lambda row: row["low"],
        "close": lambda row: row["close"],
        "volume": lambda row: row["volume"],
    }

    def staged_path(self, trade_date: date) -> Path:
        path = self._archive.staged_path(self.dataset, trade_date)
        if not path.is_file():
            msg = f"No staged bhavcopy for {trade_date.isoformat()} under {self._archive.root}"
            raise ArchiveError(msg)
        return path

    def ohlc(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        needle = symbol.strip().upper()
        series_needle = series.strip().upper()
        rows = [bar for day in self.window(from_date, to_date) for bar in self._first_match(day, needle, series_needle)]
        return self.to_frame(rows)

    def _first_match(self, day: date, needle: str, series_needle: str) -> list[OhlcRow]:
        for bar in self.rows_on(day):
            if bar["series"] == series_needle and bar["symbol"] == needle:
                return [bar]
        return []

    def on(self, trade_date: date, *, symbol: str | None = None, series: str = "EQ") -> pd.DataFrame:
        self.staged_path(trade_date)  # raises ArchiveError if the day isn't staged
        series_needle = series.strip().upper()
        symbol_needle = symbol.strip().upper() if symbol else None
        rows = [
            bar
            for bar in self.rows_on(trade_date)
            if bar["series"] == series_needle and (symbol_needle is None or bar["symbol"] == symbol_needle)
        ]
        return self.to_frame(rows)

    def latest(self, symbol: str, *, series: str = "EQ") -> pd.Series | None:
        latest_day = self.latest_date()
        if latest_day is None:
            return None
        frame = self.ohlc(symbol, from_date=latest_day, to_date=latest_day, series=series)
        return frame.iloc[0] if not frame.empty else None

    def wide_frame(
        self,
        *,
        column: str = "close",
        symbols: Iterable[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        getter = self._COLUMN_GETTERS.get(column.strip().lower())
        if getter is None:
            msg = f"column must be one of {tuple(self._COLUMN_GETTERS)}, got {column!r}"
            raise ValueError(msg)
        series_needle = series.strip().upper()
        wanted = {s.strip().upper() for s in symbols} if symbols is not None else None

        matrix: dict[date, dict[str, float]] = {}
        for day in self.window(from_date, to_date):
            row = {
                bar["symbol"]: getter(bar)
                for bar in self.rows_on(day)
                if bar["series"] == series_needle and (wanted is None or bar["symbol"] in wanted)
            }
            if row:
                matrix[day] = row

        frame = pd.DataFrame.from_dict(matrix, orient="index").sort_index()
        frame.index.name = "Date"
        return frame

    def coverage_gaps(self, *, from_date: date | None = None, to_date: date | None = None) -> list[date]:
        """XBOM sessions in the window with no staged bhavcopy file."""
        return [
            day for day in self.window(from_date, to_date) if not self._archive.staged_path(self.dataset, day).is_file()
        ]
