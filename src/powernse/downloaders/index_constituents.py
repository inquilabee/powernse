"""Download NSE index constituent snapshots into the archive staging tree."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

from powernse.archive import RAW_INDEX_CONSTITUENTS_DIR, archive_key
from powernse.constants import INDEX_CONSTITUENTS_API_URL
from powernse.downloaders.base import ArchiveDownloader
from powernse.errors import PayloadError
from powernse.types import DownloadSummary


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
        sleep_seconds: float = 0.5,
        skip_existing: bool = True,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        super().__init__(
            root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            fetch_bytes=fetch_bytes,
            default_accept="application/json",
        )

    def download_snapshot(self, trade_date: date, index_name: str) -> Path:
        """Download one index snapshot for trade_date (snapshot-as-of download time)."""
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
        for index_name in index_names:
            relative = index_constituents_staged_key(trade_date, index_name)
            if self.skip_existing and self.destination_exists(relative):
                skipped += 1
                continue
            self.download_snapshot(trade_date, index_name)
            downloaded += 1
        return DownloadSummary(downloaded_count=downloaded, skipped_existing_count=skipped)


def extract_index_constituent_records(decoded: object) -> list[object]:
    if isinstance(decoded, dict):
        data = decoded.get("data")
        if isinstance(data, list):
            return cast(list[object], data)
    if isinstance(decoded, list):
        return cast(list[object], decoded)
    msg = "Unexpected index constituents JSON shape"
    raise PayloadError(msg)


def is_eq_constituent_record(record: object) -> bool:
    if not isinstance(record, dict) or "symbol" not in record:
        return False
    return str(record.get("series") or "").upper() == "EQ"


def parse_index_constituent_symbols(payload: bytes) -> list[str]:
    """Extract EQ series symbol list from an NSE index constituents JSON payload."""
    records = extract_index_constituent_records(json.loads(payload))
    symbols: list[str] = []
    for record in records:
        if is_eq_constituent_record(record):
            symbols.append(str(cast(dict[str, object], record)["symbol"]))
    return symbols
