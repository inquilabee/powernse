"""Deep NSE index EOD history: per-index time-series sources, staged into ``index_closes``.

NSE's dated ``ind_close_all_*.csv`` archive 404s before 2012-02-21. This module reaches
back to each index's base date (~1995) through per-index historical APIs and merges the
result into the same ``raw/index_closes/YYYY/YYYY-MM-DD.csv`` layout the daily archive
uses -- so ``NSEData(root).index(name).ohlc(...)`` returns one continuous series with no
new read path.
"""

import csv
import io
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import ClassVar
from urllib.parse import urlencode

from powernse.archive import record_download
from powernse.constants import (
    INDEX_HISTORY_MAX_CHUNK_DAYS,
    NIFTY_INDICES_HISTORY_URL,
    NIFTY_INDICES_REFERER,
    NSE_INDEX_HISTORY_API_URL,
    NSE_INDEX_HISTORY_REFERER,
)
from powernse.datasets import INDEX_CLOSES
from powernse.downloaders.base import ArchiveDownloader, RootLike
from powernse.errors import DownloadError, PayloadError
from powernse.http import NseHttpClient
from powernse.types import DownloadSummary

logger = logging.getLogger(__name__)

# ``ind_close_all`` header the staged CSV must carry -- IndexClosesRowParser keys on these names.
_CSV_FIELDS = (
    "Index Name",
    "Index Date",
    "Open Index Value",
    "High Index Value",
    "Low Index Value",
    "Closing Index Value",
)
_MISSING = "-"

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


@dataclass(frozen=True, slots=True)
class IndexHistoryRow:
    """One index's EOD level for a day. OHLC is ``None`` when the source omits it (older rows)."""

    trade_date: date
    index_name: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text == _MISSING:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_day(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%d %B %Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 -- naive exchange date is intended
        except ValueError:
            continue
    return None


def _first(row: dict[str, object], *keys: str) -> object:
    for key in keys:
        if key in row and str(row[key]).strip():
            return row[key]
    return None


class HistoricalIndexSource(ABC):
    """A per-index EOD time-series backend. Subclasses fill the fetch + parse hooks."""

    name: ClassVar[str] = "history"

    def __init__(self, http: NseHttpClient) -> None:
        self._http = http

    def fetch_series(self, index_name: str, from_date: date, to_date: date) -> list[IndexHistoryRow]:
        """All EOD rows for ``index_name`` in ``[from_date, to_date]``, ascending and de-duplicated by day."""
        if from_date > to_date:
            return []
        by_day: dict[date, IndexHistoryRow] = {}
        for start, end in _chunk_range(from_date, to_date, INDEX_HISTORY_MAX_CHUNK_DAYS):
            for row in self._parse(self._fetch_chunk(index_name, start, end), index_name=index_name):
                by_day.setdefault(row.trade_date, row)
        return [by_day[day] for day in sorted(by_day)]

    @abstractmethod
    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes: ...

    @abstractmethod
    def _parse(self, payload: bytes, *, index_name: str) -> list[IndexHistoryRow]: ...


def _chunk_range(from_date: date, to_date: date, max_days: int) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    start = from_date
    step = timedelta(days=max_days - 1)
    while start <= to_date:
        end = min(start + step, to_date)
        chunks.append((start, end))
        start = end + timedelta(days=1)
    return chunks


class NseIndicesHistorySource(HistoricalIndexSource):
    """NSE ``/api/historicalOR/indicesHistory`` -- the preferred source."""

    name = "nse"

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes:
        params = {
            "indexType": index_name.upper(),
            "from": start.strftime("%d-%m-%Y"),
            "to": end.strftime("%d-%m-%Y"),
        }
        url = f"{NSE_INDEX_HISTORY_API_URL}?{urlencode(params)}"
        return self._http.fetch_bytes(
            url,
            accept="application/json",
            extra_headers={"Referer": NSE_INDEX_HISTORY_REFERER},
        )

    def _parse(self, payload: bytes, *, index_name: str) -> list[IndexHistoryRow]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PayloadError(f"NSE index history payload is not JSON for {index_name!r}") from exc
        data = decoded.get("data") if isinstance(decoded, dict) else decoded
        if isinstance(data, dict):
            data = data.get("indexCloseOnlineRecords") or []
        if not isinstance(data, list):
            raise PayloadError(f"NSE index history payload has no data list for {index_name!r}")
        rows: list[IndexHistoryRow] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            day = _parse_day(_first(item, "EOD_TIMESTAMP", "TIMESTAMP", "HistoricalDate"))
            if day is None:
                continue
            rows.append(
                IndexHistoryRow(
                    trade_date=day,
                    index_name=str(_first(item, "EOD_INDEX_NAME", "INDEX_NAME") or index_name).strip(),
                    open=_as_float(_first(item, "EOD_OPEN_INDEX_VAL", "OPEN")),
                    high=_as_float(_first(item, "EOD_HIGH_INDEX_VAL", "HIGH")),
                    low=_as_float(_first(item, "EOD_LOW_INDEX_VAL", "LOW")),
                    close=_as_float(_first(item, "EOD_CLOSE_INDEX_VAL", "CLOSE")),
                )
            )
        return rows


class NiftyIndicesHistorySource(HistoricalIndexSource):
    """NSE Indices Ltd ``Backpage.aspx/getHistoricaldatatabletoString`` -- price-index OHLC, reaches 1995."""

    name = "niftyindices"

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes:
        cinfo = (
            f"{{'name':'{index_name}','startDate':'{start:%d-%b-%Y}',"
            f"'endDate':'{end:%d-%b-%Y}','indexName':'{index_name}'}}"
        )
        body = json.dumps({"cinfo": cinfo}).encode("utf-8")
        return self._http.post_bytes(
            NIFTY_INDICES_HISTORY_URL,
            body,
            accept="application/json",
            content_type="application/json; charset=UTF-8",
            extra_headers={"X-Requested-With": "XMLHttpRequest", "Referer": NIFTY_INDICES_REFERER},
        )

    def _parse(self, payload: bytes, *, index_name: str) -> list[IndexHistoryRow]:
        try:
            decoded = json.loads(payload)
            table = decoded["d"] if isinstance(decoded, dict) else decoded
            if isinstance(table, str):
                table = json.loads(table)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise PayloadError(f"NSE Indices history payload is not the expected shape for {index_name!r}") from exc
        if not isinstance(table, list):
            return []
        rows: list[IndexHistoryRow] = []
        for item in table:
            if not isinstance(item, dict):
                continue
            day = _parse_day(_first(item, "HistoricalDate", "Date", "INDEX_DATE", "EOD_TIMESTAMP"))
            if day is None:
                continue
            rows.append(
                IndexHistoryRow(
                    trade_date=day,
                    index_name=str(_first(item, "Index Name", "INDEX_NAME", "EOD_INDEX_NAME") or index_name).strip(),
                    open=_as_float(_first(item, "Open", "OPEN", "Open Index Value")),
                    high=_as_float(_first(item, "High", "HIGH", "High Index Value")),
                    low=_as_float(_first(item, "Low", "LOW", "Low Index Value")),
                    close=_as_float(_first(item, "Close", "CLOSE", "Closing Index Value")),
                )
            )
        return rows


class IndexHistoryDownloader(ArchiveDownloader):
    """Fetch per-index EOD history and merge it into the shared ``index_closes`` day files."""

    accept: ClassVar[str] = "application/json"

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

    def _collect_series(self, index_name: str, from_date: date, to_date: date) -> list[IndexHistoryRow]:
        primary = self._sources[0].fetch_series(index_name, from_date, to_date)
        if len(self._sources) < 2:
            return primary
        earliest = primary[0].trade_date if primary else to_date
        if earliest <= from_date + timedelta(days=31):
            return primary
        try:
            fallback = self._sources[1].fetch_series(index_name, from_date, earliest - timedelta(days=1))
        except (DownloadError, PayloadError) as exc:
            # A flaky secondary source must not discard good primary rows.
            logger.warning("index history fallback source failed for %s: %s", index_name, exc)
            return primary
        by_day: dict[date, IndexHistoryRow] = {row.trade_date: row for row in fallback}
        by_day.update({row.trade_date: row for row in primary})  # primary wins on overlap
        return [by_day[day] for day in sorted(by_day)]

    def _write_days(self, rows_by_index: dict[str, list[IndexHistoryRow]]) -> tuple[int, int]:
        """Merge every index's rows into each day's CSV in a single read-modify-write per day file."""
        by_day: dict[date, list[IndexHistoryRow]] = {}
        for rows in rows_by_index.values():
            for row in rows:
                if row.close is None:  # no usable level -- can't stage an ind_close_all row
                    continue
                by_day.setdefault(row.trade_date, []).append(row)

        written = present = 0
        for day in sorted(by_day):
            key = self._archive.staged_key(INDEX_CLOSES, day)
            existing = self._read_day(key)
            changed = 0
            for row in by_day[day]:
                match = self._match_key(existing, row.index_name)
                if match is not None and self._skip_existing:
                    present += 1
                    continue
                existing[match or row.index_name] = self._csv_record(row)
                changed += 1
            if changed:
                payload = self._render_day(existing)
                self._archive.write_bytes(key, payload)
                record_download(self._archive, url="index-history", local_path=key, payload=payload)
                written += changed
        return written, present

    @staticmethod
    def _match_key(existing: dict[str, dict[str, str]], index_name: str) -> str | None:
        needle = index_name.casefold()
        return next((name for name in existing if name.casefold() == needle), None)

    def _read_day(self, key: str) -> dict[str, dict[str, str]]:
        path = self._archive.path_for(key)
        if not path.is_file():
            return {}
        with path.open(newline="", encoding="utf-8") as handle:
            return {
                (record.get("Index Name") or "").strip(): {k.strip(): (v or "") for k, v in record.items() if k}
                for record in csv.DictReader(handle)
                if (record.get("Index Name") or "").strip()
            }

    @staticmethod
    def _csv_record(row: IndexHistoryRow) -> dict[str, str]:
        # Older history is close-only; fill O/H/L from close so IndexClosesRowParser
        # (which drops a row when any O/H/L cell is "-") still yields the day.
        close = row.close
        opened = row.open if row.open is not None else close
        high = row.high if row.high is not None else close
        low = row.low if row.low is not None else close

        def cell(value: float | None) -> str:
            return _MISSING if value is None else f"{value:g}"

        return {
            "Index Name": row.index_name,
            "Index Date": row.trade_date.strftime("%d-%m-%Y"),
            "Open Index Value": cell(opened),
            "High Index Value": cell(high),
            "Low Index Value": cell(low),
            "Closing Index Value": cell(close),
        }

    @staticmethod
    def _render_day(by_name: dict[str, dict[str, str]]) -> bytes:
        # Widen the header to any extra ind_close_all columns (P/E, Volume, ...) present
        # on rows already staged, so a merge never strips them.
        fieldnames = list(_CSV_FIELDS)
        for record in by_name.values():
            fieldnames.extend(key for key in record if key not in fieldnames)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for name in sorted(by_name):
            writer.writerow({field: by_name[name].get(field, "") for field in fieldnames})
        return buffer.getvalue().encode("utf-8")
