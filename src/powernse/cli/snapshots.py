"""Snapshot and live-API download commands."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from powernse.cli.common import echo_summary, parse_iso_date
from powernse.constants import DEFAULT_INDEX_NAMES, DEFAULT_SLEEP_SECONDS
from powernse.downloaders import (
    BlockDealsDownloader,
    BulkDealsDownloader,
    CorporateActionsDownloader,
    FoSecbanDownloader,
    IndexConstituentsDownloader,
)
from powernse.settings import Settings


def register_snapshot_commands(app: typer.Typer) -> None:
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
        downloader = BulkDealsDownloader(archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict)
        echo_summary("bulk-deals", downloader.download(label_date or date.today()), downloader.root, strict=strict)

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
        downloader = BlockDealsDownloader(archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict)
        echo_summary("block-deals", downloader.download(label_date or date.today()), downloader.root, strict=strict)

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
        downloader = FoSecbanDownloader(archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict)
        echo_summary("fo-secban", downloader.download(label_date or date.today()), downloader.root, strict=strict)

    @app.command("corporate-actions")
    def corporate_actions_cmd(
        from_date: Annotated[date, typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD")],
        to_date: Annotated[date, typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD")],
        root: Annotated[Path | None, typer.Option(help="Archive root")] = None,
        skip_existing: Annotated[bool, typer.Option(help="Skip dates that already exist")] = True,
        sleep: Annotated[float, typer.Option(help="Extra sleep seconds between downloads")] = DEFAULT_SLEEP_SECONDS,
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
        echo_summary("corporate-actions", downloader.download_range(from_date, to_date), downloader.root, strict=strict)

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
        sleep: Annotated[float, typer.Option(help="Extra sleep seconds between downloads")] = DEFAULT_SLEEP_SECONDS,
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
            strict=strict,
        )
