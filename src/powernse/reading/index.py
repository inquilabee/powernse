"""Read index OHLC, constituent lists, and the set of staged index names."""

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

    def names(self, *, on: date | None = None) -> list[str]:
        """Distinct index names in the staged index-closes file for ``on`` (default: latest day)."""
        day = on or self.latest_date()
        if day is None:
            return []
        return sorted({bar["index_name"] for bar in self.rows_on(day)})

    def ohlc(self, name: str, *, from_date: date | None = None, to_date: date | None = None) -> pd.DataFrame:
        needle = name.strip().casefold()
        rows = [bar for day in self.window(from_date, to_date) for bar in self._first_match(day, needle)]
        return self.to_frame(rows)

    def latest_row(self, name: str) -> pd.Series | None:
        latest_day = self.latest_date()
        if latest_day is None:
            return None
        frame = self.ohlc(name, from_date=latest_day, to_date=latest_day)
        return frame.iloc[0] if not frame.empty else None

    def _first_match(self, day: date, needle: str) -> list[IndexRow]:
        for bar in self.rows_on(day):
            if bar["index_name"].casefold() == needle:
                return [bar]
        return []

    def symbols(self, on: date, name: str) -> list[str]:
        path = self._archive.staged_path(INDEX_CONSTITUENTS, on, discriminator=index_slug(name))
        if not path.is_file():
            msg = f"No staged index constituents for {name!r} on {on.isoformat()}"
            raise ArchiveError(msg)
        return parse_index_constituent_symbols(path.read_bytes())

    def constituent_dates(self, name: str) -> list[date]:
        """Staged constituent-snapshot dates for ``name``, ascending."""
        suffix = f"_{index_slug(name)}.json"
        dates = {
            date.fromisoformat(path.stem[:10])
            for path in self._archive.list_files(INDEX_CONSTITUENTS.raw_dir)
            if path.name.endswith(suffix)
        }
        return sorted(dates)


class Index:
    """A handle to one index over the staged archive: OHLC, constituents, and snapshot dates."""

    def __init__(self, name: str, reader: IndexReader) -> None:
        self.name = name
        self._reader = reader

    def __repr__(self) -> str:
        return f"Index({self.name!r})"

    def ohlc(self, *, from_date: date | None = None, to_date: date | None = None) -> pd.DataFrame:
        """OHLC across staged index-closes files (IndexSchema-shaped)."""
        return self._reader.ohlc(self.name, from_date=from_date, to_date=to_date)

    def latest(self) -> pd.Series | None:
        """Most recent staged close row, or ``None`` if this index has no staged data."""
        return self._reader.latest_row(self.name)

    def symbols(self, on: date) -> list[str]:
        """EQ-series constituent symbols from the staged snapshot labelled ``on``."""
        return self._reader.symbols(on, self.name)

    def constituent_dates(self) -> list[date]:
        """Dates for which a constituent snapshot of this index is staged."""
        return self._reader.constituent_dates(self.name)

    def exists(self) -> bool:
        """True when this index appears in the latest staged index-closes file."""
        needle = self.name.strip().casefold()
        return any(needle == name.casefold() for name in self._reader.names())
