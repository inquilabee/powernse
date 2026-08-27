"""NSE daily index close CSV download and staging."""

from collections.abc import Callable
from datetime import date

from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_SLEEP_SECONDS
from powernse.datasets import INDEX_CLOSES
from powernse.downloaders.dated import DatedCsvArchiveDownloader, RootLike


def index_closes_archive_url(trade_date: date) -> str:
    """Return the NSE archive URL for all-index closes on a day."""
    stamp = trade_date.strftime("%d%m%Y")
    return f"{ARCHIVE_BASE_URL}/content/indices/ind_close_all_{stamp}.csv"


class IndexClosesDownloader(DatedCsvArchiveDownloader):
    """Download daily all-index close CSV files."""

    dataset = INDEX_CLOSES
    series_label = "Index closes"

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
        return index_closes_archive_url(trade_date)
