"""Command-line interface for PowerNSE."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from requests import RequestException

from powernse.constants import DEFAULT_INDEX_NAMES, DEFAULT_RESUME_DAYS, DEFAULT_SLEEP_SECONDS
from powernse.data import NSEData
from powernse.downloaders import (
    BhavcopyDownloader,
    CorporateActionsDownloader,
    IndexConstituentsDownloader,
    resolve_bhavcopy_resume_range,
)
from powernse.errors import DownloadError, PowerNseError
from powernse.http import NseHttpClient
from powernse.settings import Settings

app = typer.Typer(
    name="powernse",
    help="Download and use official NSE India equity archives.",
    no_args_is_help=True,
)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _exit_for_summary(summary_failed: int) -> None:
    if summary_failed > 0:
        raise typer.Exit(code=1)


@app.command("bhavcopy")
def bhavcopy_cmd(
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Download from last staged date (or 2000-01-01) through today"),
    ] = False,
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
        typer.Option("--days", help="Max calendar-day span when using --resume (default: 100)"),
    ] = DEFAULT_RESUME_DAYS,
    root: Annotated[Path | None, typer.Option(help="Archive root (default: POWERNSE_ROOT or ./nse-data)")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip dates that already exist")] = True,
    sleep: Annotated[
        float,
        typer.Option(help="Extra sleep seconds between successful downloads"),
    ] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on the first unavailable trading day")] = False,
    all_calendar_days: Annotated[
        bool,
        typer.Option("--all-calendar-days", help="Walk every calendar day instead of XBOM sessions only"),
    ] = False,
) -> None:
    """Download CM bhavcopy CSV archives."""
    archive_root = Settings.resolve(root).archive_root
    if resume:
        resolved_from, resolved_to = resolve_bhavcopy_resume_range(
            archive_root,
            days=days,
            from_date=from_date,
            to_date=to_date,
        )
        typer.echo(f"bhavcopy resume: {resolved_from.isoformat()} → {resolved_to.isoformat()} (days<={days})")
    else:
        if from_date is None or to_date is None:
            typer.echo("Provide --from and --to, or use --resume", err=True)
            raise typer.Exit(code=2)
        resolved_from, resolved_to = from_date, to_date

    downloader = BhavcopyDownloader(
        archive_root,
        sleep_seconds=sleep,
        skip_existing=skip_existing,
        strict=strict,
        all_calendar_days=all_calendar_days,
    )
    summary = downloader.download_range(resolved_from, resolved_to)
    typer.echo(
        f"bhavcopy: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} failed={summary.failed_count} "
        f"root={downloader.root}"
    )
    _exit_for_summary(summary.failed_count)


@app.command("corporate-actions")
def corporate_actions_cmd(
    from_date: Annotated[date, typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD")],
    to_date: Annotated[date, typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD")],
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip dates that already exist")] = True,
    sleep: Annotated[
        float,
        typer.Option(help="Extra sleep seconds between downloads"),
    ] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on the first failure")] = False,
    all_calendar_days: Annotated[
        bool,
        typer.Option("--all-calendar-days", help="Walk every calendar day instead of XBOM sessions only"),
    ] = False,
) -> None:
    """Download corporate actions JSON by trading day."""
    archive_root = Settings.resolve(root).archive_root
    downloader = CorporateActionsDownloader(
        archive_root,
        sleep_seconds=sleep,
        skip_existing=skip_existing,
        strict=strict,
        all_calendar_days=all_calendar_days,
    )
    summary = downloader.download_range(from_date, to_date)
    typer.echo(
        f"corporate-actions: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} failed={summary.failed_count} "
        f"root={downloader.root}"
    )
    _exit_for_summary(summary.failed_count)


@app.command("index-constituents")
def index_constituents_cmd(
    label_date: Annotated[
        date | None,
        typer.Option(
            "--label-date",
            parser=parse_iso_date,
            help="Archive filename date label only (snapshot is as-of download time)",
        ),
    ] = None,
    index: Annotated[
        list[str] | None,
        typer.Option(help="Index name (repeatable). Default: NIFTY 50"),
    ] = None,
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip snapshots that already exist")] = True,
    sleep: Annotated[
        float,
        typer.Option(help="Extra sleep seconds between downloads"),
    ] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on the first failure")] = False,
) -> None:
    """Download live index constituent snapshots (as-of now; label-date is filename only)."""
    archive_root = Settings.resolve(root).archive_root
    downloader = IndexConstituentsDownloader(
        archive_root,
        sleep_seconds=sleep,
        skip_existing=skip_existing,
        strict=strict,
    )
    indices = index or list(DEFAULT_INDEX_NAMES)
    summary = downloader.download_indices(label_date or date.today(), indices)
    typer.echo(
        f"index-constituents: downloaded={summary.downloaded_count} "
        f"skipped={summary.skipped_existing_count} failed={summary.failed_count} "
        f"root={downloader.root}"
    )
    _exit_for_summary(summary.failed_count)


@app.command("status")
def status_cmd(
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
) -> None:
    """Show staged file counts under the archive root (does not create directories)."""
    data = NSEData(root, create=False)
    inventory = data.inventory()
    typer.echo(f"archive root: {data.root}")
    for key, value in inventory.items():
        typer.echo(f"  {key}: {value}")


@app.command("ohlc")
def ohlc_cmd(
    symbol: Annotated[str, typer.Argument(help="NSE ticker, e.g. RELIANCE")],
    from_date: Annotated[
        date | None,
        typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD (default: latest day)"),
    ] = None,
    to_date: Annotated[
        date | None,
        typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD (default: latest day)"),
    ] = None,
    series: Annotated[str, typer.Option(help="Security series filter")] = "EQ",
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
) -> None:
    """Print OHLC bars for one symbol from staged bhavcopy files."""
    data = NSEData(root, create=False)
    bars = data.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)
    if not bars:
        typer.echo(f"No OHLC rows for {symbol.upper()} series={series} under {data.root}", err=True)
        raise typer.Exit(code=1)
    typer.echo("trade_date,symbol,series,open,high,low,close,volume,isin")
    for bar in bars:
        isin = bar.isin or ""
        typer.echo(
            f"{bar.trade_date.isoformat()},{bar.symbol},{bar.series},"
            f"{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume},{isin}"
        )


@app.command("doctor")
def doctor_cmd() -> None:
    """Prime an NSE session and report basic connectivity."""
    client = NseHttpClient()
    try:
        payload = client.probe_home()
    except (DownloadError, RequestException, OSError) as exc:
        typer.echo(f"doctor: FAILED ({exc})", err=True)
        raise typer.Exit(code=1) from exc
    primed = "primed" if client.primed else f"not primed ({client.prime_error or 'unknown'})"
    typer.echo(f"doctor: OK ({primed}; home returned {len(payload)} bytes)")


def main(argv: list[str] | None = None) -> int:
    """Console script entry that returns an exit code."""
    try:
        result = app(args=argv, standalone_mode=False)
    except typer.Exit as exc:
        code = exc.exit_code
        return 0 if code is None else int(code)
    except (PowerNseError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        return 1
    if isinstance(result, int):
        return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
