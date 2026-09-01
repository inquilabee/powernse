"""Per-index end-of-day time-series backends for deep index history.

Each source knows one remote API: how to page a date range through it and how to
turn one page of JSON into :class:`IndexHistoryRow` values. The staging side
(merging rows into ``raw/index_closes/``) lives in :mod:`.downloader`.

Two concrete sources ship:

* :class:`NseIndicesHistorySource` -- ``www.nseindia.com/api/historicalOR/indicesHistory``,
  the preferred one. Returns the modern index name for the whole history.
* :class:`NiftyIndicesHistorySource` -- NSE Indices Ltd's ``niftyindices.com``
  price-index endpoint, used only to fill the leading gap when NSE's own series
  starts later than the requested ``from`` date (its history reaches 1995).

Response shapes were taken from public documentation, not a live capture (NSE
blocks unprimed requests), so the parsers are deliberately tolerant: they try a
list of candidate key names for each field and a list of date formats, and a row
that yields no parseable date is dropped rather than raising.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import ClassVar
from urllib.parse import urlencode

from powernse.constants import (
    INDEX_HISTORY_MAX_CHUNK_DAYS,
    NIFTY_INDICES_HISTORY_URL,
    NIFTY_INDICES_REFERER,
    NSE_INDEX_HISTORY_API_URL,
    NSE_INDEX_HISTORY_REFERER,
)
from powernse.errors import PayloadError
from powernse.http import NseHttpClient

JSON_ACCEPT = "application/json"
COMPACT_DATE = "%d-%m-%Y"  # NSE query params and the staged "Index Date" cell
ABBR_DATE = "%d-%b-%Y"  # niftyindices query params ("03-Nov-1995")
#: Date spellings seen across the two feeds ("15-DEC-2025", "03 Nov 1995", ...).
DAY_FORMATS = (ABBR_DATE, "%d %b %Y", "%d-%B-%Y", "%d %B %Y", COMPACT_DATE)
MISSING = "-"  # ind_close_all's "no value" cell; also what a blank OHLC reads back as


@dataclass(frozen=True, slots=True)
class IndexHistoryRow:
    """One index's end-of-day level for a day. OHLC is ``None`` when the source omits it."""

    trade_date: date
    index_name: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None


class HistoricalIndexSource(ABC):
    """A per-index time-series backend.

    Subclasses declare the candidate key names for each field and fill two hooks:
    :meth:`_fetch_chunk` (one HTTP call for a <=1-year span) and :meth:`_records`
    (unwrap that response to the list of raw per-day dicts). Everything else --
    range chunking, row assembly, value coercion -- is shared here.
    """

    name: ClassVar[str] = "history"
    open_keys: ClassVar[tuple[str, ...]] = ()
    high_keys: ClassVar[tuple[str, ...]] = ()
    low_keys: ClassVar[tuple[str, ...]] = ()
    close_keys: ClassVar[tuple[str, ...]] = ()
    date_keys: ClassVar[tuple[str, ...]] = ()
    name_keys: ClassVar[tuple[str, ...]] = ()

    def __init__(self, http: NseHttpClient) -> None:
        self._http = http

    def fetch_series(self, index_name: str, from_date: date, to_date: date) -> list[IndexHistoryRow]:
        """All rows for ``index_name`` in ``[from_date, to_date]``, ascending and de-duplicated by day."""
        if from_date > to_date:
            return []
        by_day: dict[date, IndexHistoryRow] = {}
        for start, end in self._chunks(from_date, to_date):
            for row in self._parse(self._fetch_chunk(index_name, start, end), index_name):
                by_day.setdefault(row.trade_date, row)
        return [by_day[day] for day in sorted(by_day)]

    def _parse(self, payload: bytes, index_name: str) -> list[IndexHistoryRow]:
        return [row for item in self._records(payload, index_name) if (row := self._row(item, index_name)) is not None]

    def _row(self, item: object, index_name: str) -> IndexHistoryRow | None:
        day = self._to_day(self._pick(item, self.date_keys))
        if day is None:  # a row we can't date is useless -- skip it
            return None
        return IndexHistoryRow(
            trade_date=day,
            index_name=str(self._pick(item, self.name_keys) or index_name).strip(),
            open=self._to_float(self._pick(item, self.open_keys)),
            high=self._to_float(self._pick(item, self.high_keys)),
            low=self._to_float(self._pick(item, self.low_keys)),
            close=self._to_float(self._pick(item, self.close_keys)),
        )

    @abstractmethod
    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes: ...

    @abstractmethod
    def _records(self, payload: bytes, index_name: str) -> list[object]:
        """Decode ``payload`` to the list of raw per-day record dicts (envelope handling lives here)."""

    @staticmethod
    def _chunks(from_date: date, to_date: date) -> list[tuple[date, date]]:
        """Split the span into contiguous <=1-year windows; the NSE endpoint rejects wider."""
        step = timedelta(days=INDEX_HISTORY_MAX_CHUNK_DAYS - 1)
        spans: list[tuple[date, date]] = []
        start = from_date
        while start <= to_date:
            end = min(start + step, to_date)
            spans.append((start, end))
            start = end + timedelta(days=1)
        return spans

    @staticmethod
    def _pick(row: object, keys: tuple[str, ...]) -> object:
        """First non-blank value among ``keys`` in ``row``, or ``None`` (also when ``row`` isn't a dict)."""
        if not isinstance(row, dict):
            return None
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return value
        return None

    @staticmethod
    def _to_float(value: object) -> float | None:
        text = str(value).strip().replace(",", "") if value is not None else ""
        if not text or text == MISSING:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _to_day(value: object) -> date | None:
        text = str(value or "").strip()
        for fmt in DAY_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()  # noqa: DTZ007 -- naive exchange date is intended
            except ValueError:
                continue
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


class NseIndicesHistorySource(HistoricalIndexSource):
    """NSE ``/api/historicalOR/indicesHistory`` -- the preferred source."""

    name = "nse"
    open_keys = ("EOD_OPEN_INDEX_VAL", "OPEN")
    high_keys = ("EOD_HIGH_INDEX_VAL", "HIGH")
    low_keys = ("EOD_LOW_INDEX_VAL", "LOW")
    close_keys = ("EOD_CLOSE_INDEX_VAL", "CLOSE")
    date_keys = ("EOD_TIMESTAMP", "TIMESTAMP", "HistoricalDate")
    name_keys = ("EOD_INDEX_NAME", "INDEX_NAME")

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes:
        params = {
            "indexType": index_name.upper(),
            "from": start.strftime(COMPACT_DATE),
            "to": end.strftime(COMPACT_DATE),
        }
        url = f"{NSE_INDEX_HISTORY_API_URL}?{urlencode(params)}"
        return self._http.fetch_bytes(url, accept=JSON_ACCEPT, extra_headers={"Referer": NSE_INDEX_HISTORY_REFERER})

    def _records(self, payload: bytes, index_name: str) -> list[object]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PayloadError(f"NSE index history payload is not JSON for {index_name!r}") from exc
        data = decoded.get("data") if isinstance(decoded, dict) else decoded
        if isinstance(data, dict):  # nested envelope: OHLC lives under indexCloseOnlineRecords
            data = data.get("indexCloseOnlineRecords") or []
        if not isinstance(data, list):
            raise PayloadError(f"NSE index history payload has no data list for {index_name!r}")
        return data


class NiftyIndicesHistorySource(HistoricalIndexSource):
    """NSE Indices Ltd ``Backpage.aspx/getHistoricaldatatabletoString`` -- price-index OHLC, reaches 1995."""

    name = "niftyindices"
    open_keys = ("Open", "OPEN", "Open Index Value")
    high_keys = ("High", "HIGH", "High Index Value")
    low_keys = ("Low", "LOW", "Low Index Value")
    close_keys = ("Close", "CLOSE", "Closing Index Value")
    date_keys = ("HistoricalDate", "Date", "INDEX_DATE", "EOD_TIMESTAMP")
    name_keys = ("Index Name", "INDEX_NAME", "EOD_INDEX_NAME")

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes:
        span = f"'startDate':'{start.strftime(ABBR_DATE)}','endDate':'{end.strftime(ABBR_DATE)}'"
        cinfo = f"{{'name':'{index_name}',{span},'indexName':'{index_name}'}}"
        body = json.dumps({"cinfo": cinfo}).encode("utf-8")
        return self._http.post_bytes(
            NIFTY_INDICES_HISTORY_URL,
            body,
            accept=JSON_ACCEPT,
            content_type="application/json; charset=UTF-8",
            extra_headers={"X-Requested-With": "XMLHttpRequest", "Referer": NIFTY_INDICES_REFERER},
        )

    def _records(self, payload: bytes, index_name: str) -> list[object]:
        try:
            decoded = json.loads(payload)
            table = decoded["d"] if isinstance(decoded, dict) else decoded
            if isinstance(table, str):  # ASP.NET double-encodes the payload
                table = json.loads(table)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise PayloadError(f"NSE Indices history payload is not the expected shape for {index_name!r}") from exc
        return table if isinstance(table, list) else []
