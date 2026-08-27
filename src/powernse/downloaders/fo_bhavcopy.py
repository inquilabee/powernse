"""NSE F&O bhavcopy archive download and staging."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import extract_csv_from_zip
from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_SLEEP_SECONDS, UDIFF_SWITCH_DATE_ISO
from powernse.datasets import FO_BHAVCOPY
from powernse.downloaders.dated import DatedCsvArchiveDownloader, RootLike

UDIFF_SWITCH_DATE = date.fromisoformat(UDIFF_SWITCH_DATE_ISO)


def fo_bhavcopy_archive_url(trade_date: date) -> str:
    """Return the NSE archive URL for a trading day's F&O bhavcopy.

    Before the UDIFF switch date, uses ``content/historical/DERIVATIVES/...``.
    On and after that date, uses ``content/fo/BhavCopy_NSE_FO_...``.
    """
    if trade_date < UDIFF_SWITCH_DATE:
        date_str = trade_date.strftime("%d%b%Y").upper()
        month = date_str[2:5]
        return f"{ARCHIVE_BASE_URL}/content/historical/DERIVATIVES/{trade_date.year}/{month}/fo{date_str}bhav.csv.zip"
    compact = trade_date.strftime("%Y%m%d")
    return f"{ARCHIVE_BASE_URL}/content/fo/BhavCopy_NSE_FO_0_0_0_{compact}_F_0000.csv.zip"


class FoBhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download F&O bhavcopy archives into the NSE archive staging tree."""

    dataset = FO_BHAVCOPY
    series_label = "F&O bhavcopy"

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
        return fo_bhavcopy_archive_url(trade_date)

    def materialize_payload(self, trade_date: date, url: str, payload: bytes) -> bytes:
        del trade_date
        preferred = Path(url).name.replace(".zip", "").replace(".ZIP", "")
        preferred_member = preferred if preferred.lower().endswith(".csv") else None
        return extract_csv_from_zip(payload, preferred_member=preferred_member)
