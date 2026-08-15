"""Template-method downloaders for dated trading-day CSV archives."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.constants import DEFAULT_SLEEP_SECONDS
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError, PayloadError
from powernse.settings import Settings
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

RootLike = Path | str | ArchiveRoot | Settings


class DatedCsvArchiveDownloader(ArchiveDownloader, ABC):
    """Shared skip / strict / summary loop for one-file-per-trading-day archives."""

    series_label: str = "archive"

    def __init__(
        self,
        root: RootLike,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
        all_calendar_days: bool = False,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        super().__init__(root, sleep_seconds=sleep_seconds, skip_existing=skip_existing, fetch_bytes=fetch_bytes)
        self._strict = strict
        self._all_calendar_days = all_calendar_days

    @abstractmethod
    def staged_key(self, trade_date: date) -> str:
        """Return the archive-relative key for ``trade_date``."""

    @abstractmethod
    def archive_url(self, trade_date: date) -> str:
        """Return the download URL for ``trade_date``."""

    def materialize_payload(self, trade_date: date, url: str, payload: bytes) -> bytes:
        """Transform raw HTTP bytes into staged CSV bytes (default: passthrough)."""
        del trade_date, url
        return payload

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        downloaded = 0
        skipped = 0
        failed = 0
        for trade_date in iter_trading_dates(from_date, to_date, all_calendar_days=self._all_calendar_days):
            key = self.staged_key(trade_date)
            if self.skip_existing and self.destination_exists(key):
                skipped += 1
                continue
            result = self._download_trade_date_or_none(trade_date)
            if result is None:
                failed += 1
            else:
                downloaded += 1
        return DownloadSummary(
            downloaded_count=downloaded,
            skipped_existing_count=skipped,
            failed_count=failed,
        )

    def _download_trade_date_or_none(self, trade_date: date) -> str | None:
        try:
            return self._download_trade_date(trade_date)
        except (DownloadError, PayloadError) as exc:
            if self._strict:
                raise
            logger.warning("Skipping %s %s: %s", self.series_label, trade_date.isoformat(), exc)
            return None

    def _download_trade_date(self, trade_date: date) -> str:
        staged_key = self.staged_key(trade_date)
        url = self.archive_url(trade_date)
        payload = self.fetch_bytes_throttled(url)
        from powernse.http import looks_like_html

        if looks_like_html(payload):
            msg = f"{self.series_label} unavailable for {trade_date.isoformat()}: {url}"
            raise DownloadError(msg)
        csv_bytes = self.materialize_payload(trade_date, url, payload)
        unavailable = f"{self.series_label} unavailable for {trade_date.isoformat()}: {url}"
        self.persist_bytes(url, staged_key, csv_bytes, unavailable_message=unavailable)
        return staged_key
