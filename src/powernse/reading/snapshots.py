"""Read snapshot CSVs (deals, F&O ban, full bhavcopy) and the archive inventory."""

import csv
from datetime import date

from powernse import datasets
from powernse.datasets import BLOCK_DEALS, BULK_DEALS, FO_SECBAN, FULL_BHAVCOPY, Dataset
from powernse.errors import ArchiveError
from powernse.reading.base import ArchiveReader

Row = dict[str, str]


class SnapshotReader(ArchiveReader):
    """The raw-CSV escape hatches: one ``list[dict]`` per staged snapshot day."""

    def full_bhavcopy_rows(self, trade_date: date) -> list[Row]:
        return self._rows(FULL_BHAVCOPY, trade_date, "full bhavcopy")

    def bulk_deals(self, label_date: date) -> list[Row]:
        return self._rows(BULK_DEALS, label_date, "bulk deals")

    def block_deals(self, label_date: date) -> list[Row]:
        return self._rows(BLOCK_DEALS, label_date, "block deals")

    def fo_secban(self, label_date: date) -> list[Row]:
        return self._rows(FO_SECBAN, label_date, "fo secban")

    def _rows(self, dataset: Dataset, day: date, label: str) -> list[Row]:
        path = self._archive.staged_path(dataset, day)
        if not path.is_file():
            msg = f"No staged {label} for {day.isoformat()} under {self._archive.root}"
            raise ArchiveError(msg)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def inventory(self) -> dict[str, int]:
        """Staged file counts by dataset, plus the manifest size."""
        counts = {ds.key: len(self._archive.list_files(ds.raw_dir)) for ds in datasets.ALL}
        counts["manifest_bytes"] = self._manifest_bytes()
        return counts

    def _manifest_bytes(self) -> int:
        path = self._archive.root / "manifest" / "downloads.jsonl"
        return path.stat().st_size if path.is_file() else 0
