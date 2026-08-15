"""Typer application entry for PowerNSE."""

import typer

from powernse.cli.bundle_cmd import register_bundle_commands
from powernse.cli.dated import register_dated_download_command
from powernse.cli.read import register_read_commands
from powernse.cli.snapshots import register_snapshot_commands
from powernse.downloaders import (  # noqa: F401 — getattr targets for dated commands / tests
    BhavcopyDownloader,
    FoBhavcopyDownloader,
    FullBhavcopyDownloader,
    IndexClosesDownloader,
    resolve_bhavcopy_resume_range,
    resolve_fo_bhavcopy_resume_range,
    resolve_full_bhavcopy_resume_range,
    resolve_index_closes_resume_range,
)
from powernse.errors import PowerNseError

app = typer.Typer(
    name="powernse",
    help="Download and use official NSE India equity archives.",
    no_args_is_help=True,
)

register_dated_download_command(
    app,
    name="bhavcopy",
    help_text="Download CM bhavcopy CSV archives.",
    downloader_attr="BhavcopyDownloader",
    resume_resolver_attr="resolve_bhavcopy_resume_range",
)
register_dated_download_command(
    app,
    name="fo-bhavcopy",
    help_text="Download F&O bhavcopy CSV archives.",
    downloader_attr="FoBhavcopyDownloader",
    resume_resolver_attr="resolve_fo_bhavcopy_resume_range",
)
register_dated_download_command(
    app,
    name="index-closes",
    help_text="Download daily all-index close CSV files.",
    downloader_attr="IndexClosesDownloader",
    resume_resolver_attr="resolve_index_closes_resume_range",
)
register_dated_download_command(
    app,
    name="full-bhavcopy",
    help_text="Download security full bhavcopy CSV (includes delivery columns).",
    downloader_attr="FullBhavcopyDownloader",
    resume_resolver_attr="resolve_full_bhavcopy_resume_range",
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
