"""``powernse index-history`` -- deep per-index EOD history into the ``index_closes`` layout."""

from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import typer

from powernse.cli.common import echo_summary, parse_iso_date
from powernse.constants import DEFAULT_SLEEP_SECONDS, INDEX_HISTORY_FROM_DATE
from powernse.datasets import INDEX_CLOSES
from powernse.downloaders import LONG_HISTORY_INDEX_NAMES, IndexHistoryDownloader
from powernse.index import load_entries
from powernse.settings import Settings

_DEFAULT_FROM = date.fromisoformat(INDEX_HISTORY_FROM_DATE)
_DEFAULT_TO = (INDEX_CLOSES.history_start or _DEFAULT_FROM) - timedelta(days=1)

_INDEX_HELP = f"Index name (repeatable). Default: {len(LONG_HISTORY_INDEX_NAMES)} long-history indices."
_ALL_HELP = "Pull every catalogued index (~2 min at --sleep 0.2). Overrides --index."


def register_index_history_command(app: typer.Typer) -> None:
    @app.command("index-history")
    def index_history_cmd(
        index: Annotated[list[str] | None, typer.Option("--index", help=_INDEX_HELP)] = None,
        all_indices: Annotated[bool, typer.Option("--all", help=_ALL_HELP)] = False,
        from_date: Annotated[
            date | None,
            typer.Option("--from", parser=parse_iso_date, help=f"Start date YYYY-MM-DD (default {_DEFAULT_FROM})"),
        ] = None,
        to_date: Annotated[
            date | None,
            typer.Option(
                "--to",
                parser=parse_iso_date,
                help=f"End date YYYY-MM-DD (default {_DEFAULT_TO}, the day before the ind_close_all floor)",
            ),
        ] = None,
        root: Annotated[Path | None, typer.Option(help="Archive root (default: POWERNSE_ROOT or ./nse-data)")] = None,
        skip_existing: Annotated[bool, typer.Option(help="Skip index/day rows already staged")] = True,
        sleep: Annotated[float, typer.Option(help="Extra sleep seconds between downloads")] = DEFAULT_SLEEP_SECONDS,
        strict: Annotated[bool, typer.Option(help="Abort on the first index that fails to download")] = False,
    ) -> None:
        """Backfill index EOD history to inception (~1995) via NSE's historical API, staged into index_closes."""
        archive_root = Settings.resolve(root).archive_root
        names = [entry.name for entry in load_entries()] if all_indices else (index or list(LONG_HISTORY_INDEX_NAMES))
        downloader = IndexHistoryDownloader(
            archive_root, sleep_seconds=sleep, skip_existing=skip_existing, strict=strict
        )
        summary = downloader.download_range(from_date or _DEFAULT_FROM, to_date or _DEFAULT_TO, names)
        echo_summary("index-history", summary, downloader.root, strict=strict)
