"""NSE bulk/block deal and F&O security-ban snapshot downloads."""

import logging
from abc import ABC
from datetime import date

from powernse.constants import ARCHIVE_BASE_URL
from powernse.datasets import BLOCK_DEALS, BULK_DEALS, FO_SECBAN, Dataset
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

BULK_DEALS_URL = f"{ARCHIVE_BASE_URL}/content/equities/bulk.csv"
BLOCK_DEALS_URL = f"{ARCHIVE_BASE_URL}/content/equities/block.csv"
FO_SECBAN_URL = f"{ARCHIVE_BASE_URL}/content/fo/fo_secban.csv"


class SnapshotCsvDownloader(ArchiveDownloader, ABC):
    """Download a current-exchange snapshot CSV and stage it under a label date."""

    dataset: Dataset
    snapshot_url: str
    snapshot_label: str

    def key_for(self, label_date: date) -> str:
        return self.archive.staged_key(self.dataset, label_date)

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
    dataset = BULK_DEALS
    snapshot_url = BULK_DEALS_URL
    snapshot_label = "Bulk deals"


class BlockDealsDownloader(SnapshotCsvDownloader):
    dataset = BLOCK_DEALS
    snapshot_url = BLOCK_DEALS_URL
    snapshot_label = "Block deals"


class FoSecbanDownloader(SnapshotCsvDownloader):
    dataset = FO_SECBAN
    snapshot_url = FO_SECBAN_URL
    snapshot_label = "F&O security ban"
