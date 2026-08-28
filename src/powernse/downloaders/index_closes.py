"""NSE daily index close CSV download and staging."""

from datetime import date

from powernse.constants import ARCHIVE_BASE_URL
from powernse.datasets import INDEX_CLOSES
from powernse.downloaders.dated import DatedCsvArchiveDownloader


class IndexClosesDownloader(DatedCsvArchiveDownloader):
    """Download daily all-index close CSV files."""

    dataset = INDEX_CLOSES
    series_label = "Index closes"

    @staticmethod
    def archive_url(trade_date: date) -> str:
        """NSE archive URL for all-index closes on a day."""
        stamp = trade_date.strftime("%d%m%Y")
        return f"{ARCHIVE_BASE_URL}/content/indices/ind_close_all_{stamp}.csv"
