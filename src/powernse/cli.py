"""Command-line interface for PowerNSE."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from requests import RequestException

from powernse.constants import DEFAULT_INDEX_NAMES, DEFAULT_RESUME_DAYS, DEFAULT_SLEEP_SECONDS
from powernse.data import NSEData
from powernse.downloaders import (
    BhavcopyDownloader,
    BlockDealsDownloader,
    BulkDealsDownloader,
    CorporateActionsDownloader,
    FoBhavcopyDownloader,
    FoSecbanDownloader,
    FullBhavcopyDownloader,
    IndexClosesDownloader,
    IndexConstituentsDownloader,
    resolve_bhavcopy_resume_range,
    resolve_fo_bhavcopy_resume_range,
    resolve_full_bhavcopy_resume_range,
    resolve_index_closes_resume_range,
)
from powernse.errors import DownloadError, PowerNseError
from powernse.http import NseHttpClient
from powernse.settings import Settings
from powernse.types import DownloadSummary

app = typer.Typer(
    name="powernse",
    help="Download and use official NSE India equity archives.",
    no_args_is_help=True,
)


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
        typer.Option(
            "--days",
            help="Max calendar-day span when --resume and --from are omitted (default: 100)",
        ),
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
    resolved_from, resolved_to = resolve_range_or_resume(
        resume=resume,
        from_date=from_date,
        to_date=to_date,
        days=days,
        archive_root=archive_root,
        resume_resolver=resolve_bhavcopy_resume_range,
        label="bhavcopy",
    )
    downloader = BhavcopyDownloader(
        archive_root,
        sleep_seconds=sleep,
        skip_existing=skip_existing,
        strict=strict,
        all_calendar_days=all_calendar_days,
    )
    echo_summary("bhavcopy", downloader.download_range(resolved_from, resolved_to), downloader.root)


@app.command("fo-bhavcopy")
def fo_bhavcopy_cmd(
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
    days: Annotated[int, typer.Option("--days", help="Max calendar-day span for --resume")] = DEFAULT_RESUME_DAYS,
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip dates that already exist")] = True,
    sleep: Annotated[float, typer.Option(help="Extra sleep seconds between downloads")] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on the first unavailable trading day")] = False,
    all_calendar_days: Annotated[
        bool,
        typer.Option("--all-calendar-days", help="Walk every calendar day instead of XBOM sessions only"),
    ] = False,
) -> None:
    """Download F&O bhavcopy CSV archives."""
    archive_root = Settings.resolve(root).archive_root
    resolved_from, resolved_to = resolve_range_or_resume(
        resume=resume,
        from_date=from_date,
        to_date=to_date,
        days=days,
        archive_root=archive_root,
        resume_resolver=resolve_fo_bhavcopy_resume_range,
        label="fo-bhavcopy",
    )
    downloader = FoBhavcopyDownloader(
        archive_root,
        sleep_seconds=sleep,
        skip_existing=skip_existing,
        strict=strict,
        all_calendar_days=all_calendar_days,
    )
    echo_summary("fo-bhavcopy", downloader.download_range(resolved_from, resolved_to), downloader.root)


@app.command("index-closes")
def index_closes_cmd(
    resume: Annotated[bool, typer.Option("--resume", help="Resume from last staged date through today")] = False,
    from_date: Annotated[
        date | None,
        typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD"),
    ] = None,
    to_date: Annotated[
        date | None,
        typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD"),
    ] = None,
    days: Annotated[int, typer.Option("--days", help="Max calendar-day span for --resume")] = DEFAULT_RESUME_DAYS,
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip dates that already exist")] = True,
    sleep: Annotated[float, typer.Option(help="Extra sleep seconds between downloads")] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on the first failure")] = False,
    all_calendar_days: Annotated[
        bool,
        typer.Option("--all-calendar-days", help="Walk every calendar day instead of XBOM sessions only"),
    ] = False,
) -> None:
    """Download daily all-index close CSV files."""
    archive_root = Settings.resolve(root).archive_root
    resolved_from, resolved_to = resolve_range_or_resume(
        resume=resume,
        from_date=from_date,
        to_date=to_date,
        days=days,
        archive_root=archive_root,
        resume_resolver=resolve_index_closes_resume_range,
        label="index-closes",
    )
    downloader = IndexClosesDownloader(
        archive_root,
        sleep_seconds=sleep,
        skip_existing=skip_existing,
        strict=strict,
        all_calendar_days=all_calendar_days,
    )
    echo_summary("index-closes", downloader.download_range(resolved_from, resolved_to), downloader.root)


@app.command("full-bhavcopy")
def full_bhavcopy_cmd(
    resume: Annotated[bool, typer.Option("--resume", help="Resume from last staged date through today")] = False,
    from_date: Annotated[
        date | None,
        typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD"),
    ] = None,
    to_date: Annotated[
        date | None,
        typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD"),
    ] = None,
    days: Annotated[int, typer.Option("--days", help="Max calendar-day span for --resume")] = DEFAULT_RESUME_DAYS,
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip dates that already exist")] = True,
    sleep: Annotated[float, typer.Option(help="Extra sleep seconds between downloads")] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on the first failure")] = False,
    all_calendar_days: Annotated[
        bool,
        typer.Option("--all-calendar-days", help="Walk every calendar day instead of XBOM sessions only"),
    ] = False,
) -> None:
    """Download security full bhavcopy CSV (includes delivery columns)."""
    archive_root = Settings.resolve(root).archive_root
    resolved_from, resolved_to = resolve_range_or_resume(
        resume=resume,
        from_date=from_date,
        to_date=to_date,
        days=days,
        archive_root=archive_root,
        resume_resolver=resolve_full_bhavcopy_resume_range,
        label="full-bhavcopy",
    )
    downloader = FullBhavcopyDownloader(
        archive_root,
        sleep_seconds=sleep,
        skip_existing=skip_existing,
        strict=strict,
        all_calendar_days=all_calendar_days,
    )
    echo_summary("full-bhavcopy", downloader.download_range(resolved_from, resolved_to), downloader.root)


@app.command("bulk-deals")
def bulk_deals_cmd(
    label_date: Annotated[
        date | None,
        typer.Option("--date", parser=parse_iso_date, help="Filename label date (snapshot is as-of download time)"),
    ] = None,
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip if labeled file exists")] = True,
    sleep: Annotated[float, typer.Option(help="Extra sleep seconds after download")] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on failure")] = False,
) -> None:
    """Download current bulk-deals snapshot (label-date is filename only)."""
    archive_root = Settings.resolve(root).archive_root
    downloader = BulkDealsDownloader(
        archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict
    )
    echo_summary("bulk-deals", downloader.download(label_date or date.today()), downloader.root)


@app.command("block-deals")
def block_deals_cmd(
    label_date: Annotated[
        date | None,
        typer.Option("--date", parser=parse_iso_date, help="Filename label date (snapshot is as-of download time)"),
    ] = None,
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip if labeled file exists")] = True,
    sleep: Annotated[float, typer.Option(help="Extra sleep seconds after download")] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on failure")] = False,
) -> None:
    """Download current block-deals snapshot (label-date is filename only)."""
    archive_root = Settings.resolve(root).archive_root
    downloader = BlockDealsDownloader(
        archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict
    )
    echo_summary("block-deals", downloader.download(label_date or date.today()), downloader.root)


@app.command("fo-secban")
def fo_secban_cmd(
    label_date: Annotated[
        date | None,
        typer.Option("--date", parser=parse_iso_date, help="Filename label date (snapshot is as-of download time)"),
    ] = None,
    root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    skip_existing: Annotated[bool, typer.Option(help="Skip if labeled file exists")] = True,
    sleep: Annotated[float, typer.Option(help="Extra sleep seconds after download")] = DEFAULT_SLEEP_SECONDS,
    strict: Annotated[bool, typer.Option(help="Abort on failure")] = False,
) -> None:
    """Download current F&O security-ban snapshot (label-date is filename only)."""
    archive_root = Settings.resolve(root).archive_root
    downloader = FoSecbanDownloader(
        archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict
    )
    echo_summary("fo-secban", downloader.download(label_date or date.today()), downloader.root)


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
    echo_summary(
        "corporate-actions",
        downloader.download_range(from_date, to_date),
        downloader.root,
    )


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
    echo_summary(
        "index-constituents",
        downloader.download_indices(label_date or date.today(), indices),
        downloader.root,
    )


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
