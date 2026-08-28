"""Read bulk / block deals and the F&O securities-in-ban snapshot."""

from datetime import date

import pandas as pd

from powernse.archive import ArchiveRoot
from powernse.datasets import FO_SECBAN, Dataset
from powernse.parsers.rows import DEAL_ROWS, DealRow
from powernse.parsers.secban import parse_secban
from powernse.reading.base import ArchiveReader, DatedFrameReader
from powernse.schemas import DEAL_SCHEMA


class DealsReader(DatedFrameReader[DealRow]):
    """One staged deals archive (bulk or block) -> a ``DealSchema``-shaped DataFrame."""

    schema = DEAL_SCHEMA
    parser = DEAL_ROWS

    def __init__(self, archive: ArchiveRoot, dataset: Dataset, label: str) -> None:
        super().__init__(archive)
        self.dataset = dataset
        self.label = label

    def deals(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        symbol: str | None = None,
        side: str | None = None,
    ) -> pd.DataFrame:
        needle = symbol.strip().upper() if symbol else None
        side_needle = side.strip().upper() if side else None
        rows = [
            row
            for day in self.window(from_date, to_date)
            for row in self.rows_on(day)
            if (needle is None or row["symbol"] == needle) and (side_needle is None or row["side"] == side_needle)
        ]
        return self.to_frame(rows)


class SecbanReader(ArchiveReader):
    """The F&O ban list, keyed by the effective trade date parsed from each file's header."""

    def banned(self, on: date | None = None) -> set[str]:
        by_date = self._by_effective_date()
        if not by_date:
            return set()
        target = on or max(by_date)
        return set(by_date.get(target, frozenset()))

    def _by_effective_date(self) -> dict[date, frozenset[str]]:
        out: dict[date, frozenset[str]] = {}
        for path in self._archive.list_files(FO_SECBAN.raw_dir):
            if FO_SECBAN.date_of(path) is None:
                continue
            effective, symbols = parse_secban(path.read_text(encoding="utf-8"))
            if effective is not None:
                out[effective] = frozenset(symbols)
        return out
