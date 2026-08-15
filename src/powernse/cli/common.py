"""Shared CLI helpers."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

import typer

from powernse.types import DownloadSummary


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def exit_for_summary(summary_failed: int) -> None:
    if summary_failed > 0:
        raise typer.Exit(code=1)


def resolve_range_or_resume(
    *,
    resume: bool,
    from_date: date | None,
    to_date: date | None,
    days: int,
    archive_root: Path,
    resume_resolver: Callable[..., tuple[date, date]],
    label: str,
) -> tuple[date, date]:
    if resume:
        resolved_from, resolved_to = resume_resolver(
            archive_root,
            days=days,
            from_date=from_date,
            to_date=to_date,
        )
        typer.echo(f"{label} resume: {resolved_from.isoformat()} → {resolved_to.isoformat()} (days<={days})")
        return resolved_from, resolved_to
    if from_date is None or to_date is None:
        typer.echo("Provide --from and --to, or use --resume", err=True)
        raise typer.Exit(code=2)
    return from_date, to_date


def echo_summary(label: str, summary: DownloadSummary, root: Path) -> None:
    typer.echo(
        f"{label}: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} failed={summary.failed_count} "
        f"root={root}"
    )
    exit_for_summary(summary.failed_count)


RESUME_HELP = (
    "Resume from last staged date through today; empty archives start at today-minus --days "
    "(not 2000-01-01). Pass --from with --resume to uncapped history."
)
