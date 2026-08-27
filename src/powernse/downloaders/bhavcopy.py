"""NSE CM bhavcopy archive download and staging."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import extract_zip_payload_to_csv_bytes
from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_SLEEP_SECONDS, UDIFF_SWITCH_DATE_ISO
from powernse.datasets import BHAVCOPY
from powernse.downloaders.dated import DatedCsvArchiveDownloader, RootLike
from powernse.http import looks_like_html

UDIFF_SWITCH_DATE = date.fromisoformat(UDIFF_SWITCH_DATE_ISO)


def bhavcopy_archive_url(trade_date: date) -> str:
    """Return the NSE archive URL for a trading day's CM bhavcopy."""
    if trade_date < UDIFF_SWITCH_DATE:
        date_str = trade_date.strftime("%d%b%Y").upper()
        month = date_str[2:5]
        return f"{ARCHIVE_BASE_URL}/content/historical/EQUITIES/{trade_date.year}/{month}/cm{date_str}bhav.csv.zip"
    compact = trade_date.strftime("%Y%m%d")
    return f"{ARCHIVE_BASE_URL}/content/cm/BhavCopy_NSE_CM_0_0_0_{compact}_F_0000.csv.zip"


class BhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download CM bhavcopy archives into the NSE archive staging tree."""

    dataset = BHAVCOPY
    series_label = "Bhavcopy"

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
        super().__init__(
            root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            strict=strict,
            all_calendar_days=all_calendar_days,
            fetch_bytes=fetch_bytes,
        )

    def archive_url(self, trade_date: date) -> str:
        return bhavcopy_archive_url(trade_date)

    def materialize_payload(self, trade_date: date, url: str, payload: bytes) -> bytes:
        del trade_date
        if looks_like_html(payload):
            from powernse.errors import DownloadError

            msg = f"Bhavcopy unavailable: {url}"
            raise DownloadError(msg)
        preferred = Path(url).name.replace(".zip", "").replace(".ZIP", "")
        preferred_member = preferred if preferred.lower().endswith(".csv") else None
        return extract_zip_payload_to_csv_bytes(payload, preferred_member=preferred_member)

    def download_day(self, trade_date: date) -> Path:
        """Download one trading day and return the staged CSV path."""
        summary_key = self._download_trade_date(trade_date)
        return self.archive.path_for(summary_key)
