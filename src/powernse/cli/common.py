"""Shared CLI helpers and reusable option types."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from powernse.types import DownloadSummary


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


# -- reusable typer.Option types -------------------------------------------------

RootOpt = Annotated[Path | None, typer.Option(help="Archive root")]
FromDateOpt = Annotated[date | None, typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD")]
ToDateOpt = Annotated[date | None, typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD")]
SeriesOpt = Annotated[str, typer.Option(help="Security series filter")]
LabelDateOpt = Annotated[
    date | None,
    typer.Option("--date", parser=parse_iso_date, help="Filename label date (snapshot is as-of download time)"),
]
SkipExistingOpt = Annotated[bool, typer.Option(help="Skip snapshots that already exist")]
SleepOpt = Annotated[float, typer.Option(help="Extra sleep seconds between downloads")]
StrictOpt = Annotated[bool, typer.Option(help="Abort on the first failure")]
AllCalendarDaysOpt = Annotated[
    bool, typer.Option("--all-calendar-days", help="Walk every calendar day instead of XBOM sessions only")
]

RESUME_HELP = (
    "Resume from last staged date through today; empty archives start at today-minus --days "
    "(not 2000-01-01). Pass --from with --resume to uncapped history."
)


def print_frame_or_exit(frame: pd.DataFrame, *, empty_message: str) -> None:
    """Echo a DataFrame as CSV, or write ``empty_message`` to stderr and exit 1."""
    if frame.empty:
        typer.echo(empty_message, err=True)
        raise typer.Exit(code=1)
    typer.echo(frame.to_csv(index=False).rstrip("\n"))


def exit_for_summary(summary_failed: int, *, strict: bool) -> None:
    if strict and summary_failed > 0:
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
        resolved_from, resolved_to = resume_resolver(archive_root, days=days, from_date=from_date, to_date=to_date)
        typer.echo(f"{label} resume: {resolved_from.isoformat()} → {resolved_to.isoformat()} (days<={days})")
        return resolved_from, resolved_to
    if from_date is None or to_date is None:
        typer.echo("Provide --from and --to, or use --resume", err=True)
        raise typer.Exit(code=2)
    return from_date, to_date


def echo_summary(label: str, summary: DownloadSummary, root: Path, *, strict: bool = False) -> None:
    typer.echo(
        f"{label}: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} failed={summary.failed_count} "
        f"root={root}"
    )
    exit_for_summary(summary.failed_count, strict=strict)
