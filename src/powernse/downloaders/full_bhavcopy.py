"""NSE security full bhavcopy (with delivery) download and staging."""

from collections.abc import Callable
from datetime import date

from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_SLEEP_SECONDS
from powernse.datasets import FULL_BHAVCOPY
from powernse.downloaders.dated import DatedCsvArchiveDownloader, RootLike


def full_bhavcopy_archive_url(trade_date: date) -> str:
    """Return the NSE archive URL for ``sec_bhavdata_full`` on a day."""
    stamp = trade_date.strftime("%d%m%Y")
    return f"{ARCHIVE_BASE_URL}/products/content/sec_bhavdata_full_{stamp}.csv"


class FullBhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download daily security full bhavcopy CSV (includes delivery columns)."""

    dataset = FULL_BHAVCOPY
    series_label = "Full bhavcopy"

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
        return full_bhavcopy_archive_url(trade_date)
