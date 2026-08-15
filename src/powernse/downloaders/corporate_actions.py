"""Download NSE corporate action reports into the archive staging tree."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

from powernse.archive import RAW_CORPORATE_ACTIONS_DIR, archive_key
from powernse.constants import CORPORATE_ACTIONS_API_URL
from powernse.downloaders.base import ArchiveDownloader
from powernse.types import DownloadSummary


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
        sleep_seconds: float = 0.5,
        skip_existing: bool = True,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        super().__init__(
            root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            fetch_bytes=fetch_bytes,
            default_accept="application/json",
        )

    def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
        if from_date > to_date:
            msg = f"from_date {from_date} must be on or before to_date {to_date}"
            raise ValueError(msg)

        downloaded = 0
        skipped = 0
        current = from_date
        while current <= to_date:
            if self._download_day_if_needed(current):
                downloaded += 1
            else:
                skipped += 1
            current += timedelta(days=1)
        return DownloadSummary(downloaded_count=downloaded, skipped_existing_count=skipped)

    def _download_day_if_needed(self, trade_date: date) -> bool:
        relative = corporate_actions_staged_key(trade_date)
        if self.skip_existing and self.destination_exists(relative):
            return False
        url = corporate_actions_request_url(trade_date, trade_date)
        self.fetch_and_persist(
            url,
            relative,
            unavailable_message=f"Corporate actions unavailable for {trade_date.isoformat()}: {url}",
        )
        return True
