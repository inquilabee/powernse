"""Read bulk / block deals and the F&O securities-in-ban snapshot."""

from datetime import date, timedelta
from typing import ClassVar

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
    #: a deal file's label date (download day) can trail its trade date by a few
    #: days (weekend / delayed run), so scan a wider label window, then filter exactly
    LABEL_SLACK: ClassVar[timedelta] = timedelta(days=7)

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
        """Deals whose parsed trade date is in ``[from_date, to_date]``.

        Deal archives are label-dated snapshots (named for the download day), not
        a per-session series -- a file downloaded on a weekend carries the prior
        session's deals. So this walks the staged files and filters the frame by
        the ``Date`` column, not by filename.
        """
        rows = self._matching_rows(self._label_dates(from_date, to_date), symbol, side)
        frame = self._within(self.to_frame(rows), from_date, to_date)
        return frame.drop_duplicates().sort_values("trade_date", kind="stable").reset_index(drop=True)

    def _matching_rows(self, days: list[date], symbol: str | None, side: str | None) -> list[DealRow]:
        needle = symbol.strip().upper() if symbol else None
        side_needle = side.strip().upper() if side else None
        return [
            row
            for day in days
            for row in self.rows_on(day)
            if (needle is None or row["symbol"] == needle) and (side_needle is None or row["side"] == side_needle)
        ]

    @staticmethod
    def _within(frame: pd.DataFrame, from_date: date | None, to_date: date | None) -> pd.DataFrame:
        if from_date is not None:
            frame = frame[frame["trade_date"] >= from_date]
        if to_date is not None:
            frame = frame[frame["trade_date"] <= to_date]
        return frame

    def _label_dates(self, from_date: date | None, to_date: date | None) -> list[date]:
        lo = from_date - self.LABEL_SLACK if from_date else None
        hi = to_date + self.LABEL_SLACK if to_date else None
        return [
            day
            for day in self._archive.staged_dates(self.dataset)
            if (lo is None or day >= lo) and (hi is None or day <= hi)
        ]


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
