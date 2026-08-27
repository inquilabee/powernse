"""NSE CM bhavcopy archive download and staging."""

from datetime import date
from pathlib import Path

from powernse.archive import extract_csv_from_zip, looks_like_html
from powernse.constants import ARCHIVE_BASE_URL, UDIFF_SWITCH_DATE_ISO
from powernse.datasets import BHAVCOPY
from powernse.downloaders.dated import DatedCsvArchiveDownloader
from powernse.errors import DownloadError

UDIFF_SWITCH_DATE = date.fromisoformat(UDIFF_SWITCH_DATE_ISO)


class BhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download CM bhavcopy archives into the NSE archive staging tree."""

    dataset = BHAVCOPY
    series_label = "Bhavcopy"

    @staticmethod
    def archive_url(trade_date: date) -> str:
        """NSE archive URL for a trading day's CM bhavcopy."""
        if trade_date < UDIFF_SWITCH_DATE:
            date_str = trade_date.strftime("%d%b%Y").upper()
            month = date_str[2:5]
            return f"{ARCHIVE_BASE_URL}/content/historical/EQUITIES/{trade_date.year}/{month}/cm{date_str}bhav.csv.zip"
        compact = trade_date.strftime("%Y%m%d")
        return f"{ARCHIVE_BASE_URL}/content/cm/BhavCopy_NSE_CM_0_0_0_{compact}_F_0000.csv.zip"

    def materialize_payload(self, trade_date: date, url: str, payload: bytes) -> bytes:
        del trade_date
        if looks_like_html(payload):
            msg = f"Bhavcopy unavailable: {url}"
            raise DownloadError(msg)
        preferred = Path(url).name.replace(".zip", "").replace(".ZIP", "")
        preferred_member = preferred if preferred.lower().endswith(".csv") else None
        return extract_csv_from_zip(payload, preferred_member=preferred_member)

    def download_day(self, trade_date: date) -> Path:
        """Download one trading day and return the staged CSV path."""
        return self.archive.path_for(self._download_trade_date(trade_date))
