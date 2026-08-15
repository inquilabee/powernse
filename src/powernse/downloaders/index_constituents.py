"""Download NSE index constituent snapshots into the archive staging tree."""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from powernse.archive import RAW_INDEX_CONSTITUENTS_DIR, archive_key
from powernse.constants import DEFAULT_SLEEP_SECONDS, INDEX_CONSTITUENTS_API_URL
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import DownloadError, PayloadError
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IndexConstituentRecord:
    """One equity constituent row from an NSE index snapshot."""

    symbol: str
    series: str


def index_slug(index_name: str) -> str:
    """Normalize an index label for filesystem paths."""
    return re.sub(r"[^a-z0-9]+", "_", index_name.strip().lower()).strip("_")


def index_constituents_request_url(index_name: str) -> str:
    """Build the NSE equity-stock-indices API URL."""
    return f"{INDEX_CONSTITUENTS_API_URL}?{urlencode({'index': index_name.upper()})}"


def index_constituents_staged_path(root: Path, trade_date: date, index_name: str) -> Path:
    """Path for a daily index constituents JSON snapshot."""
    return (
        root
        / RAW_INDEX_CONSTITUENTS_DIR
        / str(trade_date.year)
        / f"{trade_date.isoformat()}_{index_slug(index_name)}.json"
    )


def index_constituents_staged_key(trade_date: date, index_name: str) -> str:
    return archive_key(
        RAW_INDEX_CONSTITUENTS_DIR.as_posix(),
        str(trade_date.year),
        f"{trade_date.isoformat()}_{index_slug(index_name)}.json",
    )


class IndexConstituentsDownloader(ArchiveDownloader):
    """Fetch index constituent snapshots into the archive staging tree."""

    def __init__(
        self,
        root: Path | str,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        super().__init__(
            root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            fetch_bytes=fetch_bytes,
            default_accept="application/json",
        )
        self._strict = strict

    def download_range(self, trade_date: date, index_names: list[str]) -> DownloadSummary:
        """Download snapshots for each index; trade_date is an archive label only."""
        return self.download_indices(trade_date, index_names)

    def download_snapshot(self, trade_date: date, index_name: str) -> Path:
        """Download one live index snapshot labeled with trade_date."""
        relative = index_constituents_staged_key(trade_date, index_name)
        destination = self.archive.path_for(relative)
        if self.skip_existing and destination.is_file():
            return destination

        url = index_constituents_request_url(index_name)
        self.fetch_and_persist(
            url,
            relative,
            unavailable_message=f"Index constituents unavailable for {index_name!r}: {url}",
        )
        return destination

    def download_indices(self, trade_date: date, index_names: list[str]) -> DownloadSummary:
        downloaded = 0
        skipped = 0
        failed = 0
        for index_name in index_names:
            relative = index_constituents_staged_key(trade_date, index_name)
            if self.skip_existing and self.destination_exists(relative):
                skipped += 1
                continue
            try:
                self.download_snapshot(trade_date, index_name)
                downloaded += 1
            except (DownloadError, PayloadError) as exc:
                if self._strict:
                    raise
                logger.warning("Skipping index %s: %s", index_name, exc)
                failed += 1
        return DownloadSummary(
            downloaded_count=downloaded,
            skipped_existing_count=skipped,
            failed_count=failed,
        )


def parse_index_constituent_records(payload: bytes) -> list[IndexConstituentRecord]:
    """Parse NSE index constituents JSON into typed records."""
    decoded = json.loads(payload)
    raw_records = _extract_raw_records(decoded)
    records: list[IndexConstituentRecord] = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            continue
        series = str(item.get("series") or "")
        records.append(IndexConstituentRecord(symbol=symbol, series=series))
    return records


def _extract_raw_records(decoded: object) -> list[object]:
    if isinstance(decoded, dict):
        data = decoded.get("data")
        if isinstance(data, list):
            return data
    if isinstance(decoded, list):
        return decoded
    msg = "Unexpected index constituents JSON shape"
    raise PayloadError(msg)


def parse_index_constituent_symbols(payload: bytes) -> list[str]:
    """Extract EQ series symbol list from an NSE index constituents JSON payload."""
    return [record.symbol for record in parse_index_constituent_records(payload) if record.series.upper() == "EQ"]
