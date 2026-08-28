"""Snapshot and live-API download commands."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from powernse.cli.common import (
    AllCalendarDaysOpt,
    LabelDateOpt,
    RootOpt,
    SkipExistingOpt,
    SleepOpt,
    StrictOpt,
    echo_summary,
    parse_iso_date,
)
from powernse.constants import DEFAULT_INDEX_NAMES, DEFAULT_SLEEP_SECONDS
from powernse.downloaders import (
    BlockDealsDownloader,
    BulkDealsDownloader,
    CorporateActionsDownloader,
    EquityListDownloader,
    FoSecbanDownloader,
    IndexConstituentsDownloader,
)
from powernse.downloaders.deals import SnapshotCsvDownloader
from powernse.settings import Settings


def register_snapshot_commands(app: typer.Typer) -> None:
    def _run_snapshot(
        name: str,
        downloader_cls: type[SnapshotCsvDownloader],
        label_date: date | None,
        root: Path | str | None,
        *,
        skip_existing: bool,
        sleep: float,
        strict: bool,
    ) -> None:
        archive_root = Settings.resolve(root).archive_root
        downloader = downloader_cls(archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict)
        echo_summary(name, downloader.download(label_date or date.today()), downloader.root, strict=strict)

    @app.command("bulk-deals")
    def bulk_deals_cmd(
        label_date: LabelDateOpt = None,
        root: RootOpt = None,
        skip_existing: SkipExistingOpt = True,
        sleep: SleepOpt = DEFAULT_SLEEP_SECONDS,
        strict: StrictOpt = False,
    ) -> None:
        """Download current bulk-deals snapshot (label-date is filename only)."""
        _run_snapshot(
            "bulk-deals", BulkDealsDownloader, label_date, root, skip_existing=skip_existing, sleep=sleep, strict=strict
        )

    @app.command("block-deals")
    def block_deals_cmd(
        label_date: LabelDateOpt = None,
        root: RootOpt = None,
        skip_existing: SkipExistingOpt = True,
        sleep: SleepOpt = DEFAULT_SLEEP_SECONDS,
        strict: StrictOpt = False,
    ) -> None:
        """Download current block-deals snapshot (label-date is filename only)."""
        _run_snapshot(
            "block-deals",
            BlockDealsDownloader,
            label_date,
            root,
            skip_existing=skip_existing,
            sleep=sleep,
            strict=strict,
        )

    @app.command("fo-secban")
    def fo_secban_cmd(
        label_date: LabelDateOpt = None,
        root: RootOpt = None,
        skip_existing: SkipExistingOpt = True,
        sleep: SleepOpt = DEFAULT_SLEEP_SECONDS,
        strict: StrictOpt = False,
    ) -> None:
        """Download current F&O security-ban snapshot (label-date is filename only)."""
        _run_snapshot(
            "fo-secban", FoSecbanDownloader, label_date, root, skip_existing=skip_existing, sleep=sleep, strict=strict
        )

    @app.command("equity-list")
    def equity_list_cmd(
        label_date: LabelDateOpt = None,
        root: RootOpt = None,
        skip_existing: SkipExistingOpt = True,
        sleep: SleepOpt = DEFAULT_SLEEP_SECONDS,
        strict: StrictOpt = False,
    ) -> None:
        """Download the current NSE equity security master (EQUITY_L.csv; label-date is filename only)."""
        _run_snapshot(
            "equity-list",
            EquityListDownloader,
            label_date,
            root,
            skip_existing=skip_existing,
            sleep=sleep,
            strict=strict,
        )

    @app.command("corporate-actions")
    def corporate_actions_cmd(
        from_date: Annotated[date, typer.Option("--from", parser=parse_iso_date, help="Start date YYYY-MM-DD")],
        to_date: Annotated[date, typer.Option("--to", parser=parse_iso_date, help="End date YYYY-MM-DD")],
        root: RootOpt = None,
        skip_existing: SkipExistingOpt = True,
        sleep: SleepOpt = DEFAULT_SLEEP_SECONDS,
        strict: StrictOpt = False,
        all_calendar_days: AllCalendarDaysOpt = False,
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
        label_date: LabelDateOpt = None,
        index: Annotated[list[str] | None, typer.Option(help="Index name (repeatable). Default: NIFTY 50")] = None,
        root: RootOpt = None,
        skip_existing: SkipExistingOpt = True,
        sleep: SleepOpt = DEFAULT_SLEEP_SECONDS,
        strict: StrictOpt = False,
    ) -> None:
        """Download live index constituent snapshots (as-of now; label-date is filename only)."""
        archive_root = Settings.resolve(root).archive_root
        downloader = IndexConstituentsDownloader(
            archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict
        )
        indices = index or list(DEFAULT_INDEX_NAMES)
        echo_summary(
            "index-constituents",
            downloader.download_indices(label_date or date.today(), indices),
            downloader.root,
            strict=strict,
        )
