"""Official NSE security full bhavcopy (with delivery) download and staging."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import RAW_FULL_BHAVCOPY_DIR, ArchiveRoot, archive_key
from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_RESUME_DAYS, DEFAULT_SLEEP_SECONDS
from powernse.downloaders.dated import DatedCsvArchiveDownloader, RootLike
from powernse.downloaders.resume import latest_staged_iso_csv_date, resolve_dated_resume_range


def full_bhavcopy_archive_url(trade_date: date) -> str:
    """Return the official NSE archive URL for ``sec_bhavdata_full`` on a day."""
    stamp = trade_date.strftime("%d%m%Y")
    return f"{ARCHIVE_BASE_URL}/products/content/sec_bhavdata_full_{stamp}.csv"


def staged_full_bhavcopy_csv_path(root: Path, trade_date: date) -> Path:
    return root / RAW_FULL_BHAVCOPY_DIR / str(trade_date.year) / f"{trade_date.isoformat()}.csv"


def staged_full_bhavcopy_csv_key(trade_date: date) -> str:
    return archive_key(RAW_FULL_BHAVCOPY_DIR.as_posix(), str(trade_date.year), f"{trade_date.isoformat()}.csv")


def latest_staged_full_bhavcopy_date(root: Path | ArchiveRoot) -> date | None:
    return latest_staged_iso_csv_date(root, RAW_FULL_BHAVCOPY_DIR)


def resolve_full_bhavcopy_resume_range(
    root: Path | ArchiveRoot,
    *,
    today: date | None = None,
    days: int = DEFAULT_RESUME_DAYS,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    return resolve_dated_resume_range(
        root,
        RAW_FULL_BHAVCOPY_DIR,
        today=today,
        days=days,
        from_date=from_date,
        to_date=to_date,
    )


class FullBhavcopyDownloader(DatedCsvArchiveDownloader):
    """Download daily security full bhavcopy CSV (includes delivery columns)."""

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

    def staged_key(self, trade_date: date) -> str:
        return staged_full_bhavcopy_csv_key(trade_date)

    def archive_url(self, trade_date: date) -> str:
        return full_bhavcopy_archive_url(trade_date)
