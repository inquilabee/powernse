"""Read / query CLI commands over a staged archive."""

from datetime import date
from typing import Annotated

import typer
from requests import RequestException

from powernse import datasets
from powernse.cli.common import FromDateOpt, RootOpt, SeriesOpt, ToDateOpt, parse_iso_date, print_frame_or_exit
from powernse.data import NSEData
from powernse.datasets import Dataset
from powernse.errors import ArchiveError, DownloadError
from powernse.http import NseHttpClient
from powernse.index import Index

VERIFY_DEFAULT: tuple[Dataset, ...] = (
    datasets.BHAVCOPY,
    datasets.FO_BHAVCOPY,
    datasets.INDEX_CLOSES,
    datasets.FULL_BHAVCOPY,
)


def verify_targets(key: str | None) -> tuple[Dataset, ...]:
    """The datasets ``powernse verify`` should check: one named key, or the core dated archives."""
    if key is None:
        return VERIFY_DEFAULT
    for dataset in datasets.ALL:
        if dataset.key == key:
            return (dataset,)
    choices = ", ".join(dataset.key for dataset in datasets.ALL)
    typer.echo(f"unknown dataset {key!r}; choose from {choices}", err=True)
    raise typer.Exit(code=2)


def register_read_commands(app: typer.Typer) -> None:
    @app.command("status")
    def status_cmd(root: RootOpt = None) -> None:
        """Show staged file counts under the archive root (does not create directories)."""
        data = NSEData(root, create=False)
        typer.echo(f"archive root: {data.root}")
        for key, value in data.inventory().items():
            typer.echo(f"  {key}: {value}")

    @app.command("ohlc")
    def ohlc_cmd(
        symbol: Annotated[str, typer.Argument(help="NSE ticker, e.g. RELIANCE")],
        from_date: FromDateOpt = None,
        to_date: ToDateOpt = None,
        series: SeriesOpt = "EQ",
        root: RootOpt = None,
    ) -> None:
        """Print equity OHLC bars from staged CM bhavcopy (modest windows; full-file scan per day)."""
        data = NSEData(root, create=False)
        frame = data.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)
        print_frame_or_exit(frame, empty_message=f"No OHLC rows for {symbol.upper()} series={series} under {data.root}")

    @app.command("ohlc-adjusted")
    def ohlc_adjusted_cmd(
        symbol: Annotated[str, typer.Argument(help="NSE ticker")],
        from_date: FromDateOpt = None,
        to_date: ToDateOpt = None,
        series: SeriesOpt = "EQ",
        root: RootOpt = None,
    ) -> None:
        """Print equity OHLC with opt-in bonus/split/dividend adjustments from staged corporate actions."""
        data = NSEData(root, create=False)
        frame = data.ohlc_adjusted(symbol, from_date=from_date, to_date=to_date, series=series)
        print_frame_or_exit(frame, empty_message=f"No adjusted OHLC rows for {symbol.upper()} under {data.root}")

    @app.command("fo-ohlc")
    def fo_ohlc_cmd(
        symbol: Annotated[str, typer.Argument(help="Underlying ticker")],
        from_date: FromDateOpt = None,
        to_date: ToDateOpt = None,
        instrument_type: Annotated[str | None, typer.Option("--instrument", help="e.g. FUTSTK, STO")] = None,
        expiry: Annotated[date | None, typer.Option("--expiry", parser=parse_iso_date)] = None,
        strike: Annotated[float | None, typer.Option("--strike")] = None,
        option_type: Annotated[str | None, typer.Option("--option-type", help="CE or PE")] = None,
        root: RootOpt = None,
    ) -> None:
        """Print F&O bars from staged F&O bhavcopy (modest windows)."""
        data = NSEData(root, create=False)
        frame = data.fo_bars(
            symbol,
            from_date=from_date,
            to_date=to_date,
            instrument_type=instrument_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )
        print_frame_or_exit(frame, empty_message=f"No F&O rows for {symbol.upper()} under {data.root}")

    _known_opt = typer.Option("--known", "-k", help="List the bundled catalog instead of staged names")

    @app.command("indexes")
    def indexes_cmd(root: RootOpt = None, known: Annotated[bool, _known_opt] = False) -> None:
        """List index names: staged in the latest index-closes file, or (--known) the bundled catalog."""
        if known:
            for idx in Index.catalog():
                flag = "\tfno" if idx.fno else ""
                typer.echo(f"{idx.name}\t{idx.category}{flag}")
            return
        data = NSEData(root, create=False)
        names = data.indexes()
        if not names:
            typer.echo(f"No staged index closes under {data.root}", err=True)
            raise typer.Exit(code=1)
        for name in names:
            typer.echo(name)

    @app.command("index-ohlc")
    def index_ohlc_cmd(
        index_name: Annotated[str, typer.Argument(help='Index name, e.g. "Nifty 50"')],
        from_date: FromDateOpt = None,
        to_date: ToDateOpt = None,
        root: RootOpt = None,
    ) -> None:
        """Print index OHLC from staged index-closes files (modest windows)."""
        data = NSEData(root, create=False)
        frame = data.index(index_name).ohlc(from_date=from_date, to_date=to_date)
        print_frame_or_exit(frame, empty_message=f"No index rows for {index_name!r} under {data.root}")

    _dataset_opt = typer.Option("--dataset", "-d", help="One dataset key (default: the core dated archives)")

    @app.command("verify")
    def verify_cmd(
        dataset: Annotated[str | None, _dataset_opt] = None,
        from_date: FromDateOpt = None,
        to_date: ToDateOpt = None,
        root: RootOpt = None,
    ) -> None:
        """Report XBOM sessions missing from the staged archive; exit 1 if any dataset has gaps."""
        data = NSEData(root, create=False)
        missing_total = 0
        for target in verify_targets(dataset):
            try:
                gaps = data.coverage(target, from_date=from_date, to_date=to_date)
            except ArchiveError as exc:
                typer.echo(f"{target.key}: {exc}", err=True)
                continue
            missing_total += len(gaps)
            if gaps:
                shown = ", ".join(day.isoformat() for day in gaps)
                typer.echo(f"{target.key}: {len(gaps)} missing — {shown}")
            else:
                typer.echo(f"{target.key}: complete")
        if missing_total:
            raise typer.Exit(code=1)

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
