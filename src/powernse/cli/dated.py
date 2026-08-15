"""Register dated CSV download commands on the Typer app."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from powernse.cli.common import RESUME_HELP, echo_summary, parse_iso_date, resolve_range_or_resume
from powernse.constants import DEFAULT_RESUME_DAYS, DEFAULT_SLEEP_SECONDS
from powernse.settings import Settings


def register_dated_download_command(
    app: typer.Typer,
    *,
    name: str,
    help_text: str,
    downloader_attr: str,
    resume_resolver_attr: str,
) -> None:
    @app.command(name, help=help_text)
    def dated_cmd(
        resume: Annotated[bool, typer.Option("--resume", help=RESUME_HELP)] = False,
        from_date: Annotated[
            date | None,
            typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD (required unless --resume)"),
        ] = None,
        to_date: Annotated[
            date | None,
            typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD (required unless --resume)"),
        ] = None,
        days: Annotated[
            int,
            typer.Option("--days", help="Max calendar-day span when --resume and --from are omitted"),
        ] = DEFAULT_RESUME_DAYS,
        root: Annotated[Path | None, typer.Option(help="Archive root (default: POWERNSE_ROOT or ./nse-data)")] = None,
        skip_existing: Annotated[bool, typer.Option(help="Skip dates that already exist")] = True,
        sleep: Annotated[float, typer.Option(help="Extra sleep seconds between downloads")] = DEFAULT_SLEEP_SECONDS,
        strict: Annotated[bool, typer.Option(help="Abort on the first unavailable trading day")] = False,
        all_calendar_days: Annotated[
            bool,
            typer.Option("--all-calendar-days", help="Walk every calendar day instead of XBOM sessions only"),
        ] = False,
    ) -> None:
        import importlib

        app_module = importlib.import_module("powernse.cli.app")
        downloader_cls = getattr(app_module, downloader_attr)
        resume_resolver = getattr(app_module, resume_resolver_attr)
        archive_root = Settings.resolve(root).archive_root
        resolved_from, resolved_to = resolve_range_or_resume(
            resume=resume,
            from_date=from_date,
            to_date=to_date,
            days=days,
            archive_root=archive_root,
            resume_resolver=resume_resolver,
            label=name,
        )
        downloader = downloader_cls(
            archive_root,
            sleep_seconds=sleep,
            skip_existing=skip_existing,
            strict=strict,
            all_calendar_days=all_calendar_days,
        )
        echo_summary(name, downloader.download_range(resolved_from, resolved_to), downloader.root, strict=strict)

    dated_cmd.__doc__ = help_text
