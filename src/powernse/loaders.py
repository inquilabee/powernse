"""Read staged archive files into Python structures."""

import csv
import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from powernse.archive import ArchiveRoot
from powernse.downloaders.bhavcopy import latest_staged_bhavcopy_date, staged_bhavcopy_csv_path
from powernse.downloaders.corporate_actions import corporate_actions_staged_path
from powernse.downloaders.index_constituents import (
    index_constituents_staged_path,
    parse_index_constituent_symbols,
)
from powernse.errors import ArchiveError, PayloadError
from powernse.settings import Settings

if TYPE_CHECKING:
    from pandas import DataFrame


class ArchiveReader:
    """Lifecycle owner for reading staged NSE archive files."""

    def __init__(self, root: Path | str | ArchiveRoot | None = None, *, create: bool = False) -> None:
        if isinstance(root, ArchiveRoot):
            self._archive = root
        else:
            settings = Settings.resolve(root)
            if create:
                self._archive = ArchiveRoot.open(settings.archive_root)
            else:
                self._archive = ArchiveRoot.connect(settings.archive_root)

    @property
    def root(self) -> Path:
        return self._archive.root

    def bhavcopy_path(self, trade_date: date) -> Path:
        path = staged_bhavcopy_csv_path(self.root, trade_date)
        if not path.is_file():
            msg = f"No staged bhavcopy for {trade_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        return path

    def latest_bhavcopy_date(self) -> date | None:
        """Newest staged bhavcopy date under this archive, if any."""
        return latest_staged_bhavcopy_date(self._archive)

    def bhavcopy_rows(self, trade_date: date) -> list[dict[str, str]]:
        path = self.bhavcopy_path(trade_date)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def bhavcopy_frame(self, trade_date: date) -> "DataFrame":
        try:
            import pandas as pd
        except ImportError as exc:
            msg = "pandas is required for bhavcopy_frame(); install with: pip install powernse[pandas]"
            raise ImportError(msg) from exc
        return pd.read_csv(self.bhavcopy_path(trade_date))

    def corporate_actions(self, trade_date: date) -> list[dict[str, object]]:
        path = corporate_actions_staged_path(self.root, trade_date)
        if not path.is_file():
            msg = f"No staged corporate actions for {trade_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        decoded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(decoded, list):
            msg = f"Corporate actions payload must be a JSON list for {trade_date.isoformat()}"
            raise PayloadError(msg)
        records: list[dict[str, object]] = []
        for item in decoded:
            if not isinstance(item, dict):
                msg = "Corporate actions list items must be objects"
                raise PayloadError(msg)
            records.append(item)
        return records

    def index_symbols(self, trade_date: date, index_name: str) -> list[str]:
        path = index_constituents_staged_path(self.root, trade_date, index_name)
        if not path.is_file():
            msg = f"No staged index constituents for {index_name!r} on {trade_date.isoformat()}"
            raise ArchiveError(msg)
        return parse_index_constituent_symbols(path.read_bytes())

    def inventory(self) -> dict[str, int]:
        """Return file counts by archive prefix."""
        return {
            "bhavcopy": len(self._archive.list_files("raw/bhavcopy")),
            "corporate_actions": len(self._archive.list_files("raw/corporate_actions")),
            "index_constituents": len(self._archive.list_files("raw/index_constituents")),
            "manifest_bytes": self._manifest_bytes(),
        }

    def _manifest_bytes(self) -> int:
        path = self.root / "manifest" / "downloads.jsonl"
        return path.stat().st_size if path.is_file() else 0
