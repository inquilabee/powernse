"""Official NSE F&O bhavcopy archive download and staging."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import RAW_FO_BHAVCOPY_DIR, ArchiveRoot, archive_key, extract_zip_payload_to_csv_bytes
from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_RESUME_DAYS, DEFAULT_SLEEP_SECONDS, UDIFF_SWITCH_DATE_ISO
from powernse.downloaders.dated import DatedCsvArchiveDownloader, RootLike
from powernse.downloaders.resume import latest_staged_iso_csv_date, resolve_dated_resume_range

UDIFF_SWITCH_DATE = date.fromisoformat(UDIFF_SWITCH_DATE_ISO)


def fo_bhavcopy_archive_url(trade_date: date) -> str:
    """Return the official NSE archive URL for a trading day's F&O bhavcopy.

    Before the UDIFF switch date, uses ``content/historical/DERIVATIVES/...``.
    On and after that date, uses ``content/fo/BhavCopy_NSE_FO_...``.
    """
    if trade_date < UDIFF_SWITCH_DATE:
        date_str = trade_date.strftime("%d%b%Y").upper()
        month = date_str[2:5]
        return f"{ARCHIVE_BASE_URL}/content/historical/DERIVATIVES/{trade_date.year}/{month}/fo{date_str}bhav.csv.zip"
    compact = trade_date.strftime("%Y%m%d")
    return f"{ARCHIVE_BASE_URL}/content/fo/BhavCopy_NSE_FO_0_0_0_{compact}_F_0000.csv.zip"


def staged_fo_bhavcopy_csv_path(root: Path, trade_date: date) -> Path:
    return root / RAW_FO_BHAVCOPY_DIR / str(trade_date.year) / f"{trade_date.isoformat()}.csv"


def staged_fo_bhavcopy_csv_key(trade_date: date) -> str:
    return archive_key(RAW_FO_BHAVCOPY_DIR.as_posix(), str(trade_date.year), f"{trade_date.isoformat()}.csv")


def latest_staged_fo_bhavcopy_date(root: Path | ArchiveRoot) -> date | None:
    return latest_staged_iso_csv_date(root, RAW_FO_BHAVCOPY_DIR)


def resolve_fo_bhavcopy_resume_range(
    root: Path | ArchiveRoot,
    *,
    today: date | None = None,
    days: int = DEFAULT_RESUME_DAYS,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    return resolve_dated_resume_range(
        root,
        RAW_FO_BHAVCOPY_DIR,
        today=today,
        days=days,
        from_date=from_date,
        to_date=to_date,
    )


class FoBhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download F&O bhavcopy archives into the NSE archive staging tree."""

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

    def staged_key(self, trade_date: date) -> str:
        return staged_fo_bhavcopy_csv_key(trade_date)

    def archive_url(self, trade_date: date) -> str:
        return fo_bhavcopy_archive_url(trade_date)

    def materialize_payload(self, trade_date: date, url: str, payload: bytes) -> bytes:
        del trade_date
        preferred = Path(url).name.replace(".zip", "").replace(".ZIP", "")
        preferred_member = preferred if preferred.lower().endswith(".csv") else None
        return extract_zip_payload_to_csv_bytes(payload, preferred_member=preferred_member)
