"""Download NSE index constituent snapshots into the archive staging tree."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlencode

import pandas as pd

from powernse.constants import INDEX_CONSTITUENTS_API_URL
from powernse.datasets import INDEX_CONSTITUENTS
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
    """Normalize an index label for filesystem paths (shared with NSEData.index().symbols)."""
    return re.sub(r"[^a-z0-9]+", "_", index_name.strip().lower()).strip("_")


class IndexConstituentsDownloader(ArchiveDownloader):
    """Fetch index constituent snapshots into the archive staging tree."""

    accept: ClassVar[str] = "application/json"

    @staticmethod
    def request_url(index_name: str) -> str:
        """NSE equity-stock-indices API URL for one index."""
        return f"{INDEX_CONSTITUENTS_API_URL}?{urlencode({'index': index_name.upper()})}"

    def download_range(self, trade_date: date, index_names: list[str]) -> DownloadSummary:
        """Download snapshots for each index; trade_date is an archive label only."""
        return self.download_indices(trade_date, index_names)

    def download_snapshot(self, trade_date: date, index_name: str) -> Path:
        """Download one live index snapshot labeled with trade_date."""
        relative = self.archive.staged_key(INDEX_CONSTITUENTS, trade_date, discriminator=index_slug(index_name))
        destination = self.archive.path_for(relative)
        if self.skip_existing and destination.is_file():
            return destination

        url = self.request_url(index_name)
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
            relative = self.archive.staged_key(INDEX_CONSTITUENTS, trade_date, discriminator=index_slug(index_name))
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

    def extract_raw_records(decoded: object) -> list[object]:
        if isinstance(decoded, dict):
            data = decoded.get("data")
            if isinstance(data, list):
                return list(data)
        if isinstance(decoded, list):
            return list(decoded)
        msg = "Unexpected index constituents JSON shape"
        raise PayloadError(msg)

    decoded = json.loads(payload)
    raw_records = extract_raw_records(decoded)
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


def parse_index_constituent_symbols(payload: bytes) -> list[str]:
    """Extract EQ series symbol list from an NSE index constituents JSON payload."""
    return [record.symbol for record in parse_index_constituent_records(payload) if record.series.upper() == "EQ"]


def parse_index_constituent_frame(payload: bytes) -> pd.DataFrame:
    """Every constituent row from an NSE index snapshot, as staged (all raw fields: symbol,
    series, lastPrice, ffmc, ... whatever NSE's payload carries for that index)."""

    def extract_raw_records(decoded: object) -> list[object]:
        if isinstance(decoded, dict):
            data = decoded.get("data")
            if isinstance(data, list):
                return list(data)
        if isinstance(decoded, list):
            return list(decoded)
        msg = "Unexpected index constituents JSON shape"
        raise PayloadError(msg)

    raw_records = extract_raw_records(json.loads(payload))
    return pd.DataFrame([item for item in raw_records if isinstance(item, dict)])
