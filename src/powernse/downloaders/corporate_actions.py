"""Download NSE corporate action reports into the archive staging tree."""

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from powernse.archive import RAW_CORPORATE_ACTIONS_DIR, archive_key
from powernse.calendar import iter_trading_dates
from powernse.constants import CORPORATE_ACTIONS_API_URL, DEFAULT_SLEEP_SECONDS
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError, PayloadError
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)


def corporate_actions_staged_path(root: Path, trade_date: date) -> Path:
    """Path for a daily corporate actions JSON file under the archive root."""
    return root / RAW_CORPORATE_ACTIONS_DIR / str(trade_date.year) / f"{trade_date.isoformat()}.json"


def corporate_actions_staged_key(trade_date: date) -> str:
    return archive_key(
        RAW_CORPORATE_ACTIONS_DIR.as_posix(),
        str(trade_date.year),
        f"{trade_date.isoformat()}.json",
    )


def corporate_actions_request_url(from_date: date, to_date: date) -> str:
    """Build the NSE corporate actions API URL for a date span."""
    params = {
        "index": "equities",
        "from_date": from_date.strftime("%d-%m-%Y"),
        "to_date": to_date.strftime("%d-%m-%Y"),
    }
    return f"{CORPORATE_ACTIONS_API_URL}?{urlencode(params)}"


class CorporateActionsDownloader(ArchiveDownloader):
    """Fetch corporate action JSON archives into the archive root."""

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
        super().__init__(
            root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            fetch_bytes=fetch_bytes,
            default_accept="application/json",
        )
        self._strict = strict
        self._all_calendar_days = all_calendar_days

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        if from_date > to_date:
            msg = f"from_date {from_date} must be on or before to_date {to_date}"
            raise ValueError(msg)

        downloaded = 0
        skipped = 0
        failed = 0
        for trade_date in iter_trading_dates(from_date, to_date, all_calendar_days=self._all_calendar_days):
            relative = corporate_actions_staged_key(trade_date)
            if self.skip_existing and self.destination_exists(relative):
                skipped += 1
                continue
            try:
                url = corporate_actions_request_url(trade_date, trade_date)
                self.fetch_and_persist(
                    url,
                    relative,
                    unavailable_message=f"Corporate actions unavailable for {trade_date.isoformat()}: {url}",
                )
                downloaded += 1
            except (DownloadError, PayloadError) as exc:
                if self._strict:
                    raise
                logger.warning("Skipping corporate actions %s: %s", trade_date.isoformat(), exc)
                failed += 1
        return DownloadSummary(
            downloaded_count=downloaded,
            skipped_existing_count=skipped,
            failed_count=failed,
        )
