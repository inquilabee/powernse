"""Turn per-index history series into staged ``index_closes`` day files.

:class:`IndexHistoryDownloader` fetches every requested index's full series (via
the :mod:`.sources` backends), then merges the rows into the shared
``raw/index_closes/YYYY/YYYY-MM-DD.csv`` layout -- one read-modify-write per day
file, not per row. Because the files use ``ind_close_all``'s column names,
``NSEData(root).index(name).ohlc(...)`` reads the deep history with no new code
path; the shipped alias map stitches it to the renamed 2012+ rows.
"""

import csv
import io
import logging
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import ClassVar

from powernse.archive import record_download
from powernse.datasets import INDEX_CLOSES
from powernse.downloaders.base import ArchiveDownloader, RootLike
from powernse.downloaders.index_history.sources import (
    JSON_ACCEPT,
    MISSING,
    HistoricalIndexSource,
    IndexHistoryRow,
    NiftyIndicesHistorySource,
    NseIndicesHistorySource,
)
from powernse.errors import DownloadError, PayloadError
from powernse.http import NseHttpClient
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

COMPACT_DATE = "%d-%m-%Y"
#: How far after ``from_date`` the primary series may start before the fallback source fills the gap.
GAP_SLACK_DAYS = 31

# ``ind_close_all`` header the staged CSV must carry -- IndexClosesRowParser keys on these names.
IDX_NAME = "Index Name"
IDX_DATE = "Index Date"
IDX_OPEN = "Open Index Value"
IDX_HIGH = "High Index Value"
IDX_LOW = "Low Index Value"
IDX_CLOSE = "Closing Index Value"
CSV_FIELDS = (IDX_NAME, IDX_DATE, IDX_OPEN, IDX_HIGH, IDX_LOW, IDX_CLOSE)

#: Catalogued indices with real pre-2012 history -- the default set for ``powernse index-history``.
LONG_HISTORY_INDEX_NAMES: tuple[str, ...] = (
    "NIFTY 50",
    "NIFTY NEXT 50",
    "NIFTY 100",
    "NIFTY 200",
    "NIFTY 500",
    "NIFTY BANK",
    "NIFTY IT",
    "NIFTY MIDCAP 100",
    "NIFTY MIDCAP 50",
    "NIFTY PHARMA",
    "NIFTY FMCG",
    "NIFTY AUTO",
    "NIFTY METAL",
    "NIFTY REALTY",
    "NIFTY ENERGY",
    "NIFTY INFRASTRUCTURE",
    "NIFTY MNC",
    "NIFTY PSE",
    "NIFTY PSU BANK",
    "NIFTY SERVICES SECTOR",
    "NIFTY COMMODITIES",
    "NIFTY INDIA CONSUMPTION",
    "NIFTY DIVIDEND OPPORTUNITIES 50",
    "INDIA VIX",
)

DayRows = dict[str, dict[str, str]]


class IndexHistoryDownloader(ArchiveDownloader):
    """Fetch per-index history and merge it into the shared ``index_closes`` day files."""

    accept: ClassVar[str] = JSON_ACCEPT

    def __init__(
        self,
        root: RootLike,
        *,
        sleep_seconds: float | None = None,
        skip_existing: bool | None = None,
        strict: bool = False,
        sources: Sequence[HistoricalIndexSource] | None = None,
        fetch_bytes: Callable[[str], bytes] | None = None,
        post_bytes: Callable[[str, bytes], bytes] | None = None,
        http_client: NseHttpClient | None = None,
    ) -> None:
        super().__init__(
            root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            strict=strict,
            fetch_bytes=fetch_bytes,
            post_bytes=post_bytes,
            http_client=http_client,
        )
        self._sources: list[HistoricalIndexSource] = (
            list(sources)
            if sources is not None
            else [NseIndicesHistorySource(self._http), NiftyIndicesHistorySource(self._http)]
        )

    def download_range(self, from_date: date, to_date: date, index_names: Sequence[str]) -> DownloadSummary:
        if from_date > to_date:
            msg = f"from_date {from_date} must be on or before to_date {to_date}"
            raise ValueError(msg)
        rows_by_index: dict[str, list[IndexHistoryRow]] = {}
        failed = 0
        for index_name in index_names:
            try:
                rows_by_index[index_name] = self._collect_series(index_name, from_date, to_date)
            except (DownloadError, PayloadError) as exc:
                if self._strict:
                    raise
                logger.warning("Skipping index history %s: %s", index_name, exc)
                failed += 1
        written, present = self._write_days(rows_by_index)
        return DownloadSummary(downloaded_count=written, skipped_existing_count=present, failed_count=failed)

    # -- fetch ---------------------------------------------------------------

    def _collect_series(self, index_name: str, from_date: date, to_date: date) -> list[IndexHistoryRow]:
        primary = self._sources[0].fetch_series(index_name, from_date, to_date)
        gap_end = self._leading_gap_end(primary, from_date, to_date)
        if gap_end is None:
            return primary
        return self._with_fallback(index_name, from_date, gap_end, primary)

    def _leading_gap_end(self, primary: list[IndexHistoryRow], from_date: date, to_date: date) -> date | None:
        """Day before which a second source should backfill, or ``None`` when the primary already reaches ``from``."""
        if len(self._sources) < 2:
            return None
        earliest = primary[0].trade_date if primary else to_date
        if earliest <= from_date + timedelta(days=GAP_SLACK_DAYS):
            return None
        return earliest - timedelta(days=1)

    def _with_fallback(
        self, index_name: str, from_date: date, gap_end: date, primary: list[IndexHistoryRow]
    ) -> list[IndexHistoryRow]:
        try:
            fallback = self._sources[1].fetch_series(index_name, from_date, gap_end)
        except (DownloadError, PayloadError) as exc:
            # A flaky secondary source must not discard the primary's good rows.
            logger.warning("index history fallback source failed for %s: %s", index_name, exc)
            return primary
        merged: dict[date, IndexHistoryRow] = {row.trade_date: row for row in fallback}
        merged.update({row.trade_date: row for row in primary})  # primary wins on overlap
        return [merged[day] for day in sorted(merged)]

    # -- stage -------------------------------------------------------------

    def _write_days(self, rows_by_index: dict[str, list[IndexHistoryRow]]) -> tuple[int, int]:
        by_day = self._group_by_day(rows_by_index)
        written = present = 0
        for day in sorted(by_day):
            key = self._archive.staged_key(INDEX_CLOSES, day)
            existing = self._read_day(key)
            changed, skipped = self._merge_rows(existing, by_day[day])
            present += skipped
            if changed:
                self._flush_day(key, existing)
                written += changed
        return written, present

    @staticmethod
    def _group_by_day(rows_by_index: dict[str, list[IndexHistoryRow]]) -> dict[date, list[IndexHistoryRow]]:
        by_day: dict[date, list[IndexHistoryRow]] = {}
        for rows in rows_by_index.values():
            for row in rows:
                if row.close is not None:  # no level -> can't stage an ind_close_all row
                    by_day.setdefault(row.trade_date, []).append(row)
        return by_day

    def _merge_rows(self, existing: DayRows, rows: list[IndexHistoryRow]) -> tuple[int, int]:
        changed = skipped = 0
        for row in rows:
            match = self._match_key(existing, row.index_name)
            if match is not None and self._skip_existing:
                skipped += 1
                continue
            existing[match or row.index_name] = self._csv_record(row)
            changed += 1
        return changed, skipped

    def _flush_day(self, key: str, by_name: DayRows) -> None:
        payload = self._render_day(by_name)
        self._archive.write_bytes(key, payload)
        record_download(self._archive, url="index-history", local_path=key, payload=payload)

    @staticmethod
    def _match_key(existing: DayRows, index_name: str) -> str | None:
        needle = index_name.casefold()
        return next((name for name in existing if name.casefold() == needle), None)

    def _read_day(self, key: str) -> DayRows:
        path = self._archive.path_for(key)
        if not path.is_file():
            return {}
        rows: DayRows = {}
        with path.open(newline="", encoding="utf-8") as handle:
            for record in csv.DictReader(handle):
                clean = {k.strip(): (v or "") for k, v in record.items() if k}
                name = clean.get(IDX_NAME, "").strip()
                if name:
                    rows[name] = clean
        return rows

    @staticmethod
    def _csv_record(row: IndexHistoryRow) -> dict[str, str]:
        # Older history is close-only; fill O/H/L from close so IndexClosesRowParser
        # (which drops a row when any O/H/L cell is "-") still yields the day.
        close = row.close

        def cell(value: float | None) -> str:
            return MISSING if value is None else f"{value:g}"

        return {
            IDX_NAME: row.index_name,
            IDX_DATE: row.trade_date.strftime(COMPACT_DATE),
            IDX_OPEN: cell(row.open if row.open is not None else close),
            IDX_HIGH: cell(row.high if row.high is not None else close),
            IDX_LOW: cell(row.low if row.low is not None else close),
            IDX_CLOSE: cell(close),
        }

    @staticmethod
    def _render_day(by_name: DayRows) -> bytes:
        # Widen the header to any extra ind_close_all columns (P/E, Volume, ...) already
        # on staged rows, so a merge never strips them.
        fieldnames = list(CSV_FIELDS)
        for record in by_name.values():
            fieldnames.extend(key for key in record if key not in fieldnames)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for name in sorted(by_name):
            writer.writerow({field: by_name[name].get(field, "") for field in fieldnames})
        return buffer.getvalue().encode("utf-8")
