"""Read / query CLI commands over a staged archive."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from requests import RequestException

from powernse.cli.common import parse_iso_date
from powernse.data import NSEData
from powernse.errors import DownloadError
from powernse.http import NseHttpClient


def register_read_commands(app: typer.Typer) -> None:
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
        """Print equity OHLC bars from staged CM bhavcopy (modest windows; full-file scan per day)."""
        data = NSEData(root, create=False)
        frame = data.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)
        if frame.empty:
            typer.echo(f"No OHLC rows for {symbol.upper()} series={series} under {data.root}", err=True)
            raise typer.Exit(code=1)
        typer.echo(frame.to_csv(index=False).rstrip("\n"))

    @app.command("ohlc-adjusted")
    def ohlc_adjusted_cmd(
        symbol: Annotated[str, typer.Argument(help="NSE ticker")],
        from_date: Annotated[
            date | None,
            typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD"),
        ] = None,
        to_date: Annotated[
            date | None,
            typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD"),
        ] = None,
        series: Annotated[str, typer.Option(help="Security series filter")] = "EQ",
        root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    ) -> None:
        """Print equity OHLC with opt-in bonus/split/dividend adjustments from staged corporate actions."""
        data = NSEData(root, create=False)
        frame = data.ohlc_adjusted(symbol, from_date=from_date, to_date=to_date, series=series)
        if frame.empty:
            typer.echo(f"No adjusted OHLC rows for {symbol.upper()} under {data.root}", err=True)
            raise typer.Exit(code=1)
        typer.echo(frame.to_csv(index=False).rstrip("\n"))

    @app.command("fo-ohlc")
    def fo_ohlc_cmd(
        symbol: Annotated[str, typer.Argument(help="Underlying ticker")],
        from_date: Annotated[
            date | None,
            typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD"),
        ] = None,
        to_date: Annotated[
            date | None,
            typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD"),
        ] = None,
        instrument_type: Annotated[str | None, typer.Option("--instrument", help="e.g. FUTSTK, STO")] = None,
        expiry: Annotated[date | None, typer.Option("--expiry", parser=parse_iso_date)] = None,
        strike: Annotated[float | None, typer.Option("--strike")] = None,
        option_type: Annotated[str | None, typer.Option("--option-type", help="CE or PE")] = None,
        root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
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
        if frame.empty:
            typer.echo(f"No F&O rows for {symbol.upper()} under {data.root}", err=True)
            raise typer.Exit(code=1)
        typer.echo(frame.to_csv(index=False).rstrip("\n"))

    @app.command("index-ohlc")
    def index_ohlc_cmd(
        index_name: Annotated[str, typer.Argument(help='Index name, e.g. "Nifty 50"')],
        from_date: Annotated[
            date | None,
            typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD"),
        ] = None,
        to_date: Annotated[
            date | None,
            typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD"),
        ] = None,
        root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
    ) -> None:
        """Print index OHLC from staged index-closes files (modest windows)."""
        data = NSEData(root, create=False)
        frame = data.index_ohlc(index_name, from_date=from_date, to_date=to_date)
        if frame.empty:
            typer.echo(f"No index rows for {index_name!r} under {data.root}", err=True)
            raise typer.Exit(code=1)
        typer.echo(frame.to_csv(index=False).rstrip("\n"))

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
