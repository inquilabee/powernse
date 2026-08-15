"""Resume helpers for dated CSV archives under a raw/ prefix."""

import re
from datetime import date, timedelta
from pathlib import Path

from powernse.archive import ArchiveRoot
from powernse.constants import DEFAULT_RESUME_DAYS, EMPTY_ARCHIVE_FROM_DATE

STAGED_ISO_CSV_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.csv$")
EMPTY_ARCHIVE_FROM = date.fromisoformat(EMPTY_ARCHIVE_FROM_DATE)


def latest_staged_iso_csv_date(root: Path | ArchiveRoot, relative_dir: Path) -> date | None:
    """Return the newest ``YYYY-MM-DD.csv`` under ``relative_dir``, or None."""
    archive = root if isinstance(root, ArchiveRoot) else ArchiveRoot.connect(root)
    latest: date | None = None
    for path in archive.list_files(relative_dir):
        match = STAGED_ISO_CSV_NAME.match(path.name)
        if match is None:
            continue
        candidate = date.fromisoformat(match.group(1))
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def resolve_dated_resume_range(
    root: Path | ArchiveRoot,
    relative_dir: Path,
    *,
    today: date | None = None,
    days: int = DEFAULT_RESUME_DAYS,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    """Resolve resume window: last staged (or 2000-01-01) → today.

    ``days`` caps the window only when ``from_date`` is omitted.
    """
    if days < 1:
        msg = f"--days must be >= 1, got {days}"
        raise ValueError(msg)
    resolved_to = to_date or (today or date.today())
    resolved_from = (
        from_date if from_date is not None else (latest_staged_iso_csv_date(root, relative_dir) or EMPTY_ARCHIVE_FROM)
    )
    if from_date is None:
        floor = resolved_to - timedelta(days=days)
        if resolved_from < floor:
            resolved_from = floor
    if resolved_from > resolved_to:
        msg = f"resume from_date {resolved_from} is after to_date {resolved_to}"
        raise ValueError(msg)
    return resolved_from, resolved_to
