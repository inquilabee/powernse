"""NSE F&O bhavcopy archive download and staging."""

from datetime import date
from pathlib import Path

from powernse.archive import extract_csv_from_zip
from powernse.constants import ARCHIVE_BASE_URL, UDIFF_SWITCH_DATE_ISO
from powernse.datasets import FO_BHAVCOPY
from powernse.downloaders.dated import DatedCsvArchiveDownloader

UDIFF_SWITCH_DATE = date.fromisoformat(UDIFF_SWITCH_DATE_ISO)


class FoBhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download F&O bhavcopy archives into the NSE archive staging tree."""

    dataset = FO_BHAVCOPY
    series_label = "F&O bhavcopy"

    @staticmethod
    def archive_url(trade_date: date) -> str:
        """NSE archive URL for a trading day's F&O bhavcopy.

        Before the UDIFF switch date, ``content/historical/DERIVATIVES/...``;
        on and after, ``content/fo/BhavCopy_NSE_FO_...``.
        """
        if trade_date < UDIFF_SWITCH_DATE:
            date_str = trade_date.strftime("%d%b%Y").upper()
            month = date_str[2:5]
            legacy = f"content/historical/DERIVATIVES/{trade_date.year}/{month}/fo{date_str}bhav.csv.zip"
            return f"{ARCHIVE_BASE_URL}/{legacy}"
        compact = trade_date.strftime("%Y%m%d")
        return f"{ARCHIVE_BASE_URL}/content/fo/BhavCopy_NSE_FO_0_0_0_{compact}_F_0000.csv.zip"

    def materialize_payload(self, trade_date: date, url: str, payload: bytes) -> bytes:
        del trade_date
        preferred = Path(url).name.replace(".zip", "").replace(".ZIP", "")
        preferred_member = preferred if preferred.lower().endswith(".csv") else None
        return extract_csv_from_zip(payload, preferred_member=preferred_member)
