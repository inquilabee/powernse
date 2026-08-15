"""Official NSE daily index close CSV download and staging."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from powernse.archive import RAW_INDEX_CLOSES_DIR, ArchiveRoot, archive_key
from powernse.constants import ARCHIVE_BASE_URL, DEFAULT_RESUME_DAYS, DEFAULT_SLEEP_SECONDS
from powernse.downloaders.dated import DatedCsvArchiveDownloader, RootLike
from powernse.downloaders.resume import latest_staged_iso_csv_date, resolve_dated_resume_range


def index_closes_archive_url(trade_date: date) -> str:
    """Return the official NSE archive URL for all-index closes on a day."""
    stamp = trade_date.strftime("%d%m%Y")
    return f"{ARCHIVE_BASE_URL}/content/indices/ind_close_all_{stamp}.csv"


def staged_index_closes_csv_path(root: Path, trade_date: date) -> Path:
    return root / RAW_INDEX_CLOSES_DIR / str(trade_date.year) / f"{trade_date.isoformat()}.csv"


def staged_index_closes_csv_key(trade_date: date) -> str:
    return archive_key(RAW_INDEX_CLOSES_DIR.as_posix(), str(trade_date.year), f"{trade_date.isoformat()}.csv")


def latest_staged_index_closes_date(root: Path | ArchiveRoot) -> date | None:
    return latest_staged_iso_csv_date(root, RAW_INDEX_CLOSES_DIR)


def resolve_index_closes_resume_range(
    root: Path | ArchiveRoot,
    *,
    today: date | None = None,
    days: int = DEFAULT_RESUME_DAYS,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    return resolve_dated_resume_range(
        root,
        RAW_INDEX_CLOSES_DIR,
        today=today,
        days=days,
        from_date=from_date,
        to_date=to_date,
    )


class IndexClosesDownloader(DatedCsvArchiveDownloader):
    """Download daily all-index close CSV files."""

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

    def staged_key(self, trade_date: date) -> str:
        return staged_index_closes_csv_key(trade_date)

    def archive_url(self, trade_date: date) -> str:
        return index_closes_archive_url(trade_date)
