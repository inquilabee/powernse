"""Read the NSE equity security master (``EQUITY_L``) out of the staged archive."""

import pandas as pd

from powernse.datasets import EQUITY_LIST
from powernse.parsers.rows import SECURITY_ROWS, SecurityRow
from powernse.reading.base import DatedFrameReader
from powernse.schemas import SECURITY_SCHEMA, empty_frame


class SecurityMasterReader(DatedFrameReader[SecurityRow]):
    """Symbol / ISIN / name / listing-date master, from the latest staged ``equity_list`` file."""

    dataset = EQUITY_LIST
    schema = SECURITY_SCHEMA
    parser = SECURITY_ROWS
    label = "equity list"

    def table(self) -> pd.DataFrame:
        """The whole security master as a ``SecuritySchema``-shaped frame (latest staged file)."""
        day = self.latest_date()
        if day is None:
            return empty_frame(self.schema)
        return self.to_frame(list(self.rows_on(day)))

    def one(self, symbol: str) -> pd.Series | None:
        needle = symbol.strip().upper()
        return self._match("symbol", needle)

    def by_isin(self, isin: str) -> pd.Series | None:
        needle = isin.strip().upper()
        return self._match("isin", needle)

    def _match(self, column: str, needle: str) -> pd.Series | None:
        frame = self.table()
        hit = frame[frame[column] == needle]
        return hit.iloc[0] if not hit.empty else None
