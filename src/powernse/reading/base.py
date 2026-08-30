"""Shared scaffolding for the archive readers."""

import csv
from abc import ABC
from collections.abc import Iterator
from datetime import date

import pandas as pd
from pdschema import Schema

from powernse.archive import ArchiveRoot
from powernse.datasets import Dataset
from powernse.parsers.rows import RowParser, SchemaRow
from powernse.schemas import empty_frame
from powernse.window import DateWindow


class ArchiveReader:
    """Base for every reader behind :class:`~powernse.data.NSEData`: holds the archive root."""

    def __init__(self, archive: ArchiveRoot) -> None:
        self._archive = archive


class DatedFrameReader[RowT: SchemaRow](ArchiveReader, ABC):
    """One-file-per-trading-day staged CSV -> a validated, schema-shaped DataFrame."""

    dataset: Dataset
    schema: Schema
    parser: RowParser[RowT]
    label: str

    def latest_date(self) -> date | None:
        return self._archive.latest_staged_date(self.dataset)

    def window(self, from_date: date | None, to_date: date | None) -> DateWindow:
        return DateWindow.resolve(
            from_date,
            to_date,
            latest=self.latest_date(),
            missing=f"No staged {self.label} under {self._archive.root}; download data first",
        )

    def rows_on(self, day: date) -> Iterator[RowT]:
        """Parsed rows from one staged day, or nothing when that day isn't staged."""
        path = self._archive.staged_path(self.dataset, day)
        if not path.is_file():
            return
        with path.open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                # NSE headers carry stray leading spaces (" SERIES", " DATE1", ...)
                clean = {key.strip(): value for key, value in raw.items() if key is not None}
                row = self.parser.from_row(clean, trade_date=day)
                if row is not None:
                    yield row

    def iter_frames(
        self, from_date: date | None = None, to_date: date | None = None
    ) -> Iterator[tuple[date, pd.DataFrame]]:
        """One validated, schema-shaped frame per *staged* day in the window, yielded lazily.

        Iterates the dataset's own staged dates -- for a per-session archive those
        are trading days; for a label-dated snapshot archive (deals) they are the
        download days.
        """
        window = self.window(from_date, to_date)
        for day in self._archive.staged_dates(self.dataset):
            if window.start <= day <= window.end:
                yield day, self.to_frame(list(self.rows_on(day)))

    def to_frame(self, rows: list[RowT]) -> pd.DataFrame:
        if not rows:
            return empty_frame(self.schema)
        frame = pd.DataFrame(rows, columns=list(self.schema.columns))
        self._finalize(frame)
        self.schema.validate(frame)
        return frame

    def _finalize(self, frame: pd.DataFrame) -> None:
        """Hook: dtype fixups before schema validation. Default: nothing."""
