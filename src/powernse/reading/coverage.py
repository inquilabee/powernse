"""Which staged sessions are missing for a dataset over a window."""

from datetime import date

from powernse.datasets import Dataset
from powernse.errors import ArchiveError
from powernse.reading.base import ArchiveReader
from powernse.window import DateWindow


class CoverageReader(ArchiveReader):
    """XBOM sessions in a window that have no staged file for a given dataset."""

    def missing(self, dataset: Dataset, *, from_date: date | None = None, to_date: date | None = None) -> list[date]:
        """Gap dates for ``dataset``. The window defaults to its full staged span."""
        staged = self._archive.staged_dates(dataset)
        empty = f"No staged {dataset.key} under {self._archive.root}; download data first"
        if not staged:
            raise ArchiveError(empty)
        window = DateWindow.resolve(from_date or staged[0], to_date or staged[-1], latest=staged[-1], missing=empty)
        return [day for day in window if not self._archive.has_staged(dataset, day)]
