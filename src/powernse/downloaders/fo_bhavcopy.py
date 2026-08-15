"""Official NSE F&O bhavcopy archive download and staging."""

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import RAW_FO_BHAVCOPY_DIR, ArchiveRoot, archive_key, extract_zip_payload_to_csv_bytes
from powernse.calendar import iter_trading_dates
from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_RESUME_DAYS, DEFAULT_SLEEP_SECONDS
from powernse.downloaders.base import ArchiveDownloader
from powernse.downloaders.resume import latest_staged_iso_csv_date, resolve_dated_resume_range
from powernse.errors import DownloadError, PayloadError
from powernse.http import looks_like_html
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)


def fo_bhavcopy_archive_url(trade_date: date) -> str:
    """Return the official NSE archive URL for a trading day's F&O bhavcopy."""
    compact = trade_date.strftime("%Y%m%d")
    return f"{ARCHIVE_BASE_URL}/content/fo/BhavCopy_NSE_FO_0_0_0_{compact}_F_0000.csv.zip"


def staged_fo_bhavcopy_csv_path(root: Path, trade_date: date) -> Path:
    return root / RAW_FO_BHAVCOPY_DIR / str(trade_date.year) / f"{trade_date.isoformat()}.csv"


def staged_fo_bhavcopy_csv_key(trade_date: date) -> str:
    return archive_key(RAW_FO_BHAVCOPY_DIR.as_posix(), str(trade_date.year), f"{trade_date.isoformat()}.csv")


def latest_staged_fo_bhavcopy_date(root: Path | ArchiveRoot) -> date | None:
    return latest_staged_iso_csv_date(root, RAW_FO_BHAVCOPY_DIR)


def resolve_fo_bhavcopy_resume_range(
    root: Path | ArchiveRoot,
    *,
    today: date | None = None,
    days: int = DEFAULT_RESUME_DAYS,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    return resolve_dated_resume_range(
        root,
        RAW_FO_BHAVCOPY_DIR,
        today=today,
        days=days,
        from_date=from_date,
        to_date=to_date,
    )


class FoBhavcopyDownloader(ArchiveDownloader):
    """Download F&O bhavcopy archives into the NSE archive staging tree."""

    def __init__(
        self,
        root: Path | str,
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

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        downloaded = 0
        skipped = 0
        failed = 0
        for trade_date in iter_trading_dates(from_date, to_date, all_calendar_days=self._all_calendar_days):
            staged_key = staged_fo_bhavcopy_csv_key(trade_date)
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

    def _download_trade_date_or_none(self, trade_date: date) -> str | None:
        try:
            return self._download_trade_date(trade_date)
        except (DownloadError, PayloadError) as exc:
            if self._strict:
                raise
            logger.warning("Skipping F&O %s: %s", trade_date.isoformat(), exc)
            return None

    def _download_trade_date(self, trade_date: date) -> str:
        staged_key = staged_fo_bhavcopy_csv_key(trade_date)
        url = fo_bhavcopy_archive_url(trade_date)
        payload = self.fetch_bytes_throttled(url)
        if looks_like_html(payload):
            msg = f"F&O bhavcopy unavailable for {trade_date.isoformat()}: {url}"
            raise DownloadError(msg)
        preferred = Path(url).name.replace(".zip", "").replace(".ZIP", "")
        preferred_member = preferred if preferred.lower().endswith(".csv") else None
        csv_bytes = extract_zip_payload_to_csv_bytes(payload, preferred_member=preferred_member)
        unavailable = f"F&O bhavcopy unavailable for {trade_date.isoformat()}: {url}"
        self.persist_bytes(url, staged_key, csv_bytes, unavailable_message=unavailable)
        return staged_key
