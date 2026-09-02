"""Index OHLC / constituent-list / staged-name reads over a local archive."""

from collections.abc import Sequence
from datetime import date

import pandas as pd

from powernse.datasets import INDEX_CLOSES, INDEX_CONSTITUENTS
from powernse.downloaders import index_slug, parse_index_constituent_frame, parse_index_constituent_symbols
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

    def ohlc(
        self,
        name: str,
        *,
        aliases: Sequence[str] = (),
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> pd.DataFrame:
        needles = self._needles(name, aliases)
        rows = [bar for day in self.window(from_date, to_date) for bar in self._first_match(day, needles)]
        return self.to_frame(rows)

    def latest_row(self, name: str, *, aliases: Sequence[str] = ()) -> pd.Series | None:
        latest_day = self.latest_date()
        if latest_day is None:
            return None
        frame = self.ohlc(name, aliases=aliases, from_date=latest_day, to_date=latest_day)
        return frame.iloc[0] if not frame.empty else None

    @staticmethod
    def _needles(name: str, aliases: Sequence[str]) -> frozenset[str]:
        """Case-folded name set an ``index_name`` cell may equal -- the query plus any past names."""
        return frozenset({name.strip().casefold(), *(alias.strip().casefold() for alias in aliases)})

    def _first_match(self, day: date, needles: frozenset[str]) -> list[IndexRow]:
        for bar in self.rows_on(day):
            if bar["index_name"].casefold() in needles:
                return [bar]
        return []

    def symbols(self, on: date, name: str) -> list[str]:
        return parse_index_constituent_symbols(self._constituents_payload(on, name))

    def constituents(self, on: date, name: str) -> pd.DataFrame:
        """Every staged constituent row for ``name`` on ``on`` (symbol, series, lastPrice,
        ffmc, ... whatever fields NSE's snapshot carries), as a plain DataFrame."""
        return parse_index_constituent_frame(self._constituents_payload(on, name))

    def _constituents_payload(self, on: date, name: str) -> bytes:
        path = self._archive.staged_path(INDEX_CONSTITUENTS, on, discriminator=index_slug(name))
        if not path.is_file():
            msg = f"No staged index constituents for {name!r} on {on.isoformat()}"
            raise ArchiveError(msg)
        return path.read_bytes()

    def constituent_dates(self, name: str) -> list[date]:
        """Staged constituent-snapshot dates for ``name``, ascending."""
        suffix = f"_{index_slug(name)}.json"
        dates = {
            date.fromisoformat(path.stem[:10])
            for path in self._archive.list_files(INDEX_CONSTITUENTS.raw_dir)
            if path.name.endswith(suffix)
        }
        return sorted(dates)
