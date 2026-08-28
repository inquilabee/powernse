"""Read F&O bars out of staged F&O bhavcopy days."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from powernse.datasets import FO_BHAVCOPY
from powernse.parsers.rows import FO_BHAVCOPY_ROWS, FoRow
from powernse.reading.base import DatedFrameReader
from powernse.schemas import FO_SCHEMA


@dataclass(frozen=True, slots=True)
class FoFilter:
    """The optional contract selectors for :meth:`FoReader.fo_bars`."""

    symbol: str
    instrument_type: str | None = None
    expiry: date | None = None
    strike: float | None = None
    option_type: str | None = None

    def matches(self, bar: FoRow) -> bool:
        return (
            bar["symbol"] == self.symbol
            and self._field_ok(bar["instrument_type"], self.instrument_type)
            and self._field_ok(bar["expiry"], self.expiry)
            and self._field_ok(bar["option_type"], self.option_type)
            and self._strike_ok(bar["strike"])
        )

    @staticmethod
    def _field_ok(value: object, wanted: object) -> bool:
        return wanted is None or value == wanted

    def _strike_ok(self, value: float | None) -> bool:
        return self.strike is None or (value is not None and abs(value - self.strike) <= 1e-9)


class FoReader(DatedFrameReader[FoRow]):
    dataset = FO_BHAVCOPY
    schema = FO_SCHEMA
    parser = FO_BHAVCOPY_ROWS
    label = "F&O bhavcopy"

    def fo_bars(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        instrument_type: str | None = None,
        expiry: date | None = None,
        strike: float | None = None,
        option_type: str | None = None,
    ) -> pd.DataFrame:
        selector = FoFilter(
            symbol=symbol.strip().upper(),
            instrument_type=instrument_type.strip().upper() if instrument_type else None,
            expiry=expiry,
            strike=strike,
            option_type=option_type.strip().upper() if option_type else None,
        )
        rows = [bar for day in self.window(from_date, to_date) for bar in self.rows_on(day) if selector.matches(bar)]
        return self.to_frame(rows)

    def _finalize(self, frame: pd.DataFrame) -> None:
        frame["open_interest"] = frame["open_interest"].astype("Int64")
