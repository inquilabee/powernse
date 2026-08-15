"""Official NSE CM bhavcopy archive download and staging."""

from __future__ import annotations

import io
import logging
import zipfile
from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import RAW_BHAVCOPY_DIR, archive_key
from powernse.calendar import iter_trading_dates
from powernse.constants import ARCHIVE_BASE_URL, UDIFF_SWITCH_DATE_ISO
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError, PayloadError
from powernse.http import looks_like_html
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

UDIFF_SWITCH_DATE = date.fromisoformat(UDIFF_SWITCH_DATE_ISO)


def bhavcopy_archive_url(trade_date: date) -> str:
    """Return the official NSE archive URL for a trading day's CM bhavcopy."""
    if trade_date < UDIFF_SWITCH_DATE:
        date_str = trade_date.strftime("%d%b%Y").upper()
        month = date_str[2:5]
        return f"{ARCHIVE_BASE_URL}/content/historical/EQUITIES/{trade_date.year}/{month}/cm{date_str}bhav.csv.zip"
    compact = trade_date.strftime("%Y%m%d")
    return f"{ARCHIVE_BASE_URL}/content/cm/BhavCopy_NSE_CM_0_0_0_{compact}_F_0000.csv.zip"


def staged_bhavcopy_csv_path(root: Path, trade_date: date) -> Path:
    """Path for extracted daily bhavcopy CSV under the archive root."""
    return root / RAW_BHAVCOPY_DIR / str(trade_date.year) / f"{trade_date.isoformat()}.csv"


def staged_bhavcopy_csv_key(trade_date: date) -> str:
    return archive_key(RAW_BHAVCOPY_DIR.as_posix(), str(trade_date.year), f"{trade_date.isoformat()}.csv")


def extract_zip_payload_to_csv_bytes(payload: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not members:
            msg = "No CSV member in bhavcopy archive"
            raise PayloadError(msg)
        with archive.open(members[0]) as source:
            return source.read()


class BhavcopyDownloader(ArchiveDownloader):
    """Download CM bhavcopy archives into the NSE archive staging tree."""

    def __init__(
        self,
        root: Path | str,
        *,
        sleep_seconds: float = 0.5,
        skip_existing: bool = True,
        strict: bool = False,
        include_weekends: bool = False,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        super().__init__(root, sleep_seconds=sleep_seconds, skip_existing=skip_existing, fetch_bytes=fetch_bytes)
        self._strict = strict
        self._include_weekends = include_weekends

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        downloaded = 0
        skipped = 0
        failed = 0
        for trade_date in iter_trading_dates(from_date, to_date, include_weekends=self._include_weekends):
            staged_key = staged_bhavcopy_csv_key(trade_date)
            if self.skip_existing and self.destination_exists(staged_key):
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

    def download_day(self, trade_date: date) -> Path:
        """Download one trading day and return the staged CSV path."""
        summary_key = self._download_trade_date(trade_date)
        return self.archive.path_for(summary_key)

    def _download_trade_date_or_none(self, trade_date: date) -> str | None:
        try:
            return self._download_trade_date(trade_date)
        except (DownloadError, PayloadError, RuntimeError) as exc:
            if self._strict:
                raise
            logger.warning("Skipping %s: %s", trade_date.isoformat(), exc)
            return None

    def _download_trade_date(self, trade_date: date) -> str:
        staged_key = staged_bhavcopy_csv_key(trade_date)
        url = bhavcopy_archive_url(trade_date)
        payload = self.fetch_bytes_throttled(url)
        if looks_like_html(payload):
            msg = f"Bhavcopy unavailable for {trade_date.isoformat()}: {url}"
            raise DownloadError(msg)
        csv_bytes = extract_zip_payload_to_csv_bytes(payload)
        unavailable = f"Bhavcopy unavailable for {trade_date.isoformat()}: {url}"
        self.persist_bytes(url, staged_key, csv_bytes, unavailable_message=unavailable)
        return staged_key
