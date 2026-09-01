"""Resume helpers for dated CSV archives."""

from datetime import date, timedelta
from pathlib import Path

from powernse.archive import ArchiveRoot
from powernse.constants import DEFAULT_RESUME_DAYS, EMPTY_ARCHIVE_FROM_DATE
from powernse.datasets import Dataset

EMPTY_ARCHIVE_FROM = date.fromisoformat(EMPTY_ARCHIVE_FROM_DATE)


def resolve_dated_resume_range(
    root: Path | ArchiveRoot,
    dataset: Dataset,
    *,
    today: date | None = None,
    days: int = DEFAULT_RESUME_DAYS,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[date, date]:
    """Resolve resume window: last staged date (or empty-archive floor) -> today.

    When ``from_date`` is omitted, ``days`` caps how far back from ``to_date`` the
    window may start (empty archives therefore begin at today-minus ``days``, not
    at the empty-archive epoch alone). Pass ``from_date`` for uncapped history.
    """
    if days < 1:
        msg = f"--days must be >= 1, got {days}"
        raise ValueError(msg)
    archive = root if isinstance(root, ArchiveRoot) else ArchiveRoot.connect(root)
    resolved_to = to_date or (today or date.today())
    resolved_from = from_date if from_date is not None else (archive.latest_staged_date(dataset) or EMPTY_ARCHIVE_FROM)
    if from_date is None:
        floor = resolved_to - timedelta(days=days)
        resolved_from = max(resolved_from, floor)
    if resolved_from > resolved_to:
        msg = f"resume from_date {resolved_from} is after to_date {resolved_to}"
        raise ValueError(msg)
    return resolved_from, resolved_to


def resolve_dated_backfill_range(
    root: Path | ArchiveRoot,
    dataset: Dataset,
    *,
    today: date | None = None,
) -> tuple[date, date]:
    """Resolve the window *before* what is staged: the source's known start -> earliest staged day.

    ``--resume`` only ever walks forward from today, so a fresh archive (or one
    seeded with a recent slice) can never reach a source's deep history. This
    fills that leading gap: from ``dataset.history_start`` (or the empty-archive
    floor) up to the day before the earliest staged file -- or up to today when
    nothing is staged yet. ``skip_existing`` still guards already-present days.
    """
    archive = root if isinstance(root, ArchiveRoot) else ArchiveRoot.connect(root)
    floor = dataset.history_start or EMPTY_ARCHIVE_FROM
    earliest = archive.earliest_staged_date(dataset)
    end = (earliest - timedelta(days=1)) if earliest is not None else (today or date.today())
    if floor > end:
        reached = f"the earliest staged day is {earliest.isoformat()}" if earliest else f"today is {end.isoformat()}"
        msg = f"{dataset.key}: nothing to backfill -- source starts {floor.isoformat()} and {reached}"
        raise ValueError(msg)
    return floor, end
