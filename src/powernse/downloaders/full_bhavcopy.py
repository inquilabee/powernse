"""NSE security full bhavcopy (with delivery) download and staging."""

from datetime import date

from powernse.constants import ARCHIVE_BASE_URL
from powernse.datasets import FULL_BHAVCOPY
from powernse.downloaders.dated import DatedCsvArchiveDownloader


class FullBhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download daily security full bhavcopy CSV (includes delivery columns)."""

    dataset = FULL_BHAVCOPY
    series_label = "Full bhavcopy"

    @staticmethod
    def archive_url(trade_date: date) -> str:
        """NSE archive URL for ``sec_bhavdata_full`` on a day."""
        stamp = trade_date.strftime("%d%m%Y")
        return f"{ARCHIVE_BASE_URL}/products/content/sec_bhavdata_full_{stamp}.csv"
