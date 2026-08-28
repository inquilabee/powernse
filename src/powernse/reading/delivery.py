"""Read delivery / traded-value data out of staged ``sec_bhavdata_full`` days."""

from collections.abc import Callable, Iterable
from datetime import date
from typing import ClassVar

import pandas as pd

from powernse.datasets import FULL_BHAVCOPY
from powernse.parsers.rows import DELIVERY_ROWS, DeliveryRow
from powernse.reading.base import DatedFrameReader
from powernse.schemas import DELIVERY_SCHEMA


class DeliveryReader(DatedFrameReader[DeliveryRow]):
    """Delivery quantity/percent, turnover, and trade count per symbol per day."""

    dataset = FULL_BHAVCOPY
    schema = DELIVERY_SCHEMA
    parser = DELIVERY_ROWS
    label = "full bhavcopy"

    _WIDE_COLUMNS: ClassVar[dict[str, Callable[[DeliveryRow], float | None]]] = {
        "delivery_pct": lambda row: row["delivery_pct"],
        "delivery_qty": lambda row: row["delivery_qty"],
        "turnover_lacs": lambda row: row["turnover_lacs"],
        "volume": lambda row: row["volume"],
    }

    def _finalize(self, frame: pd.DataFrame) -> None:
        # nullable-int column: a plain int col with any None upcasts to float64
        frame["delivery_qty"] = frame["delivery_qty"].astype("Int64")

    def delivery(
        self, symbol: str, *, from_date: date | None = None, to_date: date | None = None, series: str = "EQ"
    ) -> pd.DataFrame:
        needle = symbol.strip().upper()
        series_needle = series.strip().upper()
        rows = [row for day in self.window(from_date, to_date) for row in self._first_match(day, needle, series_needle)]
        return self.to_frame(rows)

    def _first_match(self, day: date, needle: str, series_needle: str) -> list[DeliveryRow]:
        for row in self.rows_on(day):
            if row["series"] == series_needle and row["symbol"] == needle:
                return [row]
        return []

    def on(self, trade_date: date, *, symbol: str | None = None, series: str | None = "EQ") -> pd.DataFrame:
        series_needle = series.strip().upper() if series else None
        symbol_needle = symbol.strip().upper() if symbol else None
        rows = [
            row
            for row in self.rows_on(trade_date)
            if (series_needle is None or row["series"] == series_needle)
            and (symbol_needle is None or row["symbol"] == symbol_needle)
        ]
        return self.to_frame(rows)

    def wide_frame(
        self,
        *,
        column: str = "delivery_pct",
        symbols: Iterable[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        getter = self._WIDE_COLUMNS.get(column.strip().lower())
        if getter is None:
            msg = f"column must be one of {tuple(self._WIDE_COLUMNS)}, got {column!r}"
            raise ValueError(msg)
        series_needle = series.strip().upper()
        wanted = {s.strip().upper() for s in symbols} if symbols is not None else None

        matrix: dict[date, dict[str, float | None]] = {}
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
