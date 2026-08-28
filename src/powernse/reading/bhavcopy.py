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
        key = column.strip().lower()
        return self.wide_frames(columns=(key,), symbols=symbols, from_date=from_date, to_date=to_date, series=series)[
            key
        ]

    def wide_frames(
        self,
        *,
        columns: Iterable[str],
        symbols: Iterable[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> dict[str, pd.DataFrame]:
        """One Date x Symbol matrix per requested OHLCV column, all in a single pass over staged days."""
        getters = self._resolve_getters(columns)
        series_needle = series.strip().upper()
        wanted = {s.strip().upper() for s in symbols} if symbols is not None else None
        matrices: dict[str, dict[date, dict[str, float]]] = {key: {} for key in getters}
        for day in self.window(from_date, to_date):
            for key, row in self._day_columns(day, getters, series_needle, wanted).items():
                matrices[key][day] = row
        return {key: self._as_matrix(cells) for key, cells in matrices.items()}

    def _day_columns(
        self,
        day: date,
        getters: dict[str, Callable[[OhlcRow], float]],
        series_needle: str,
        wanted: set[str] | None,
    ) -> dict[str, dict[str, float]]:
        todays = [
            bar
            for bar in self.rows_on(day)
            if bar["series"] == series_needle and (wanted is None or bar["symbol"] in wanted)
        ]
        return {key: row for key, getter in getters.items() if (row := {bar["symbol"]: getter(bar) for bar in todays})}

    def _resolve_getters(self, columns: Iterable[str]) -> dict[str, Callable[[OhlcRow], float]]:
        keys = tuple(dict.fromkeys(name.strip().lower() for name in columns))
        if not keys:
            msg = "columns must be non-empty"
            raise ValueError(msg)
        try:
            return {key: self._COLUMN_GETTERS[key] for key in keys}
        except KeyError as exc:
            msg = f"column must be one of {tuple(self._COLUMN_GETTERS)}, got {exc.args[0]!r}"
            raise ValueError(msg) from exc

    @staticmethod
    def _as_matrix(cells: dict[date, dict[str, float]]) -> pd.DataFrame:
        frame = pd.DataFrame.from_dict(cells, orient="index").sort_index()
        frame.index.name = "Date"
        return frame
