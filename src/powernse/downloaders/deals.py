"""NSE bulk/block deal and F&O security-ban snapshot downloads."""

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import (
    RAW_BLOCK_DEALS_DIR,
    RAW_BULK_DEALS_DIR,
    RAW_FO_SECBAN_DIR,
    archive_key,
)
from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_SLEEP_SECONDS
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

BULK_DEALS_URL = f"{ARCHIVE_BASE_URL}/content/equities/bulk.csv"
BLOCK_DEALS_URL = f"{ARCHIVE_BASE_URL}/content/equities/block.csv"
FO_SECBAN_URL = f"{ARCHIVE_BASE_URL}/content/fo/fo_secban.csv"


def staged_bulk_deals_csv_path(root: Path, label_date: date) -> Path:
    return root / RAW_BULK_DEALS_DIR / str(label_date.year) / f"{label_date.isoformat()}.csv"


def staged_block_deals_csv_path(root: Path, label_date: date) -> Path:
    return root / RAW_BLOCK_DEALS_DIR / str(label_date.year) / f"{label_date.isoformat()}.csv"


def staged_fo_secban_csv_path(root: Path, label_date: date) -> Path:
    return root / RAW_FO_SECBAN_DIR / str(label_date.year) / f"{label_date.isoformat()}.csv"


def staged_bulk_deals_csv_key(label_date: date) -> str:
    return archive_key(RAW_BULK_DEALS_DIR.as_posix(), str(label_date.year), f"{label_date.isoformat()}.csv")


def staged_block_deals_csv_key(label_date: date) -> str:
    return archive_key(RAW_BLOCK_DEALS_DIR.as_posix(), str(label_date.year), f"{label_date.isoformat()}.csv")


def staged_fo_secban_csv_key(label_date: date) -> str:
    return archive_key(RAW_FO_SECBAN_DIR.as_posix(), str(label_date.year), f"{label_date.isoformat()}.csv")


class SnapshotCsvDownloader(ArchiveDownloader):
    """Download a current-exchange snapshot CSV and stage it under a label date."""

    snapshot_url: str
    snapshot_label: str

    def key_for(self, label_date: date) -> str:
        raise NotImplementedError

    def __init__(
        self,
        root: Path | str,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        super().__init__(root, sleep_seconds=sleep_seconds, skip_existing=skip_existing, fetch_bytes=fetch_bytes)
        self._strict = strict

    def download(self, label_date: date) -> DownloadSummary:
        staged_key = self.key_for(label_date)
        if self.skip_existing and self.destination_exists(staged_key):
            return DownloadSummary(downloaded_count=0, skipped_existing_count=1, failed_count=0)
        try:
            unavailable = f"{self.snapshot_label} unavailable: {self.snapshot_url}"
            self.fetch_and_persist(self.snapshot_url, staged_key, unavailable_message=unavailable)
        except DownloadError:
            if self._strict:
                raise
            logger.warning("Skipping %s for %s", self.snapshot_label, label_date.isoformat())
            return DownloadSummary(downloaded_count=0, skipped_existing_count=0, failed_count=1)
        return DownloadSummary(downloaded_count=1, skipped_existing_count=0, failed_count=0)


class BulkDealsDownloader(SnapshotCsvDownloader):
    snapshot_url = BULK_DEALS_URL
    snapshot_label = "Bulk deals"

    def key_for(self, label_date: date) -> str:
        return staged_bulk_deals_csv_key(label_date)


class BlockDealsDownloader(SnapshotCsvDownloader):
    snapshot_url = BLOCK_DEALS_URL
    snapshot_label = "Block deals"

    def key_for(self, label_date: date) -> str:
        return staged_block_deals_csv_key(label_date)


class FoSecbanDownloader(SnapshotCsvDownloader):
    snapshot_url = FO_SECBAN_URL
    snapshot_label = "F&O security ban"

    def key_for(self, label_date: date) -> str:
        return staged_fo_secban_csv_key(label_date)
