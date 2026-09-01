"""Typer application entry for PowerNSE."""

from typing import Annotated

import typer

from powernse import datasets, package_version
from powernse.cli.bundle_cmd import register_bundle_commands
from powernse.cli.dated import register_dated_download_command
from powernse.cli.read import register_read_commands
from powernse.cli.snapshots import register_snapshot_commands
from powernse.downloaders import (  # noqa: F401 — getattr targets for dated commands / tests
    BhavcopyDownloader,
    FoBhavcopyDownloader,
    FullBhavcopyDownloader,
    IndexClosesDownloader,
)
from powernse.errors import PowerNseError

app = typer.Typer(
    name="powernse",
    help="Download and use NSE India end-of-day equity archives.",
    no_args_is_help=True,
)


def print_version(value: bool) -> None:
    """Eager ``--version`` handler: print the installed version and exit."""
    if value:
        typer.echo(package_version())
        raise typer.Exit()


@app.callback()
def main_options(
    version: Annotated[
        bool,
        typer.Option("--version", callback=print_version, is_eager=True, help="Show the version and exit."),
    ] = False,
) -> None:
    """Download and use NSE India end-of-day equity archives."""


register_dated_download_command(
    app,
    name="bhavcopy",
    help_text="Download CM bhavcopy CSV archives.",
    downloader_attr="BhavcopyDownloader",
    dataset=datasets.BHAVCOPY,
)
register_dated_download_command(
    app,
    name="fo-bhavcopy",
    help_text="Download F&O bhavcopy CSV archives.",
    downloader_attr="FoBhavcopyDownloader",
    dataset=datasets.FO_BHAVCOPY,
)
register_dated_download_command(
    app,
    name="index-closes",
    help_text="Download daily all-index close CSV files.",
    downloader_attr="IndexClosesDownloader",
    dataset=datasets.INDEX_CLOSES,
)
register_dated_download_command(
    app,
    name="full-bhavcopy",
    help_text="Download security full bhavcopy CSV (includes delivery columns).",
    downloader_attr="FullBhavcopyDownloader",
    dataset=datasets.FULL_BHAVCOPY,
)
register_snapshot_commands(app)
register_bundle_commands(app)
register_read_commands(app)


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
