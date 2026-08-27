"""Read index OHLC and index-constituent symbol lists."""

from datetime import date

import pandas as pd

from powernse.datasets import INDEX_CLOSES, INDEX_CONSTITUENTS
from powernse.downloaders import index_slug, parse_index_constituent_symbols
from powernse.errors import ArchiveError
from powernse.parsers.rows import INDEX_CLOSES_ROWS, IndexRow
from powernse.reading.base import DatedFrameReader
from powernse.schemas import INDEX_SCHEMA


class IndexReader(DatedFrameReader[IndexRow]):
    dataset = INDEX_CLOSES
    schema = INDEX_SCHEMA
    parser = INDEX_CLOSES_ROWS
    label = "index closes"

    def index_ohlc(
        self,
        index_name: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> pd.DataFrame:
        needle = index_name.strip().casefold()
        rows = [bar for day in self.window(from_date, to_date) for bar in self._first_match(day, needle)]
        return self.to_frame(rows)

    def _first_match(self, day: date, needle: str) -> list[IndexRow]:
        for bar in self.rows_on(day):
            if bar["index_name"].casefold() == needle:
                return [bar]
        return []

    def index_symbols(self, trade_date: date, index_name: str) -> list[str]:
        path = self._archive.staged_path(INDEX_CONSTITUENTS, trade_date, discriminator=index_slug(index_name))
        if not path.is_file():
            msg = f"No staged index constituents for {index_name!r} on {trade_date.isoformat()}"
            raise ArchiveError(msg)
        return parse_index_constituent_symbols(path.read_bytes())
