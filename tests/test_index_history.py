"""Deep index-history sources + staging into the shared index_closes layout."""

import json
from datetime import date
from pathlib import Path

from support import staged_path

from powernse.data import NSEData
from powernse.datasets import INDEX_CLOSES
from powernse.downloaders import LONG_HISTORY_INDEX_NAMES
from powernse.downloaders.index_history import (
    HistoricalIndexSource,
    IndexHistoryDownloader,
    IndexHistoryRow,
    NiftyIndicesHistorySource,
    NseIndicesHistorySource,
)
from powernse.errors import DownloadError
from powernse.index import lookup

_NSE_FLAT = {
    "data": [
        {
            "EOD_INDEX_NAME": "NIFTY 50",
            "EOD_OPEN_INDEX_VAL": 1000.0,
            "EOD_HIGH_INDEX_VAL": 1010.0,
            "EOD_LOW_INDEX_VAL": 990.0,
            "EOD_CLOSE_INDEX_VAL": 1005.5,
            "EOD_TIMESTAMP": "15-DEC-2025",
        },
        {
            "EOD_INDEX_NAME": "NIFTY 50",
            "EOD_OPEN_INDEX_VAL": "-",
            "EOD_HIGH_INDEX_VAL": "-",
            "EOD_LOW_INDEX_VAL": "-",
            "EOD_CLOSE_INDEX_VAL": "1000.00",
            "EOD_TIMESTAMP": "03-NOV-1995",
        },
        {"EOD_INDEX_NAME": "NIFTY 50", "EOD_CLOSE_INDEX_VAL": "1", "EOD_TIMESTAMP": ""},
    ]
}


def _nse_source() -> NseIndicesHistorySource:
    src = object.__new__(NseIndicesHistorySource)
    src._http = None  # type: ignore[attr-defined]  -- _parse never touches it
    return src


def test_nse_parse_flat_envelope() -> None:
    src = _nse_source()
    rows = src._parse(json.dumps(_NSE_FLAT).encode(), index_name="NIFTY 50")
    assert [r.trade_date for r in rows] == [date(2025, 12, 15), date(1995, 11, 3)]
    assert rows[0].close == 1005.5
    assert rows[1].open is None and rows[1].close == 1000.0


def test_nse_parse_nested_envelope_matches_flat() -> None:
    nested = {"data": {"indexCloseOnlineRecords": _NSE_FLAT["data"], "indexTurnoverRecords": []}}
    src = _nse_source()
    flat = src._parse(json.dumps(_NSE_FLAT).encode(), index_name="NIFTY 50")
    got = src._parse(json.dumps(nested).encode(), index_name="NIFTY 50")
    assert [(r.trade_date, r.close) for r in got] == [(r.trade_date, r.close) for r in flat]


def test_fetch_series_chunks_wide_range() -> None:
    calls: list[tuple[date, date]] = []

    class _Chunked(NseIndicesHistorySource):
        def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes:
            calls.append((start, end))
            row = {
                "EOD_INDEX_NAME": index_name,
                "EOD_CLOSE_INDEX_VAL": "1",
                "EOD_TIMESTAMP": start.strftime("%d-%b-%Y"),
            }
            return json.dumps({"data": [row]}).encode()

    src = _Chunked(http=None)  # type: ignore[arg-type]
    rows = src.fetch_series("NIFTY 50", date(2018, 1, 1), date(2020, 3, 1))
    assert len(calls) == 3
    assert calls[0][0] == date(2018, 1, 1)
    for (_, prev_end), (next_start, _) in zip(calls, calls[1:], strict=False):
        assert (next_start - prev_end).days == 1
    assert rows == sorted(rows, key=lambda r: r.trade_date)


def test_niftyindices_parse_double_encoded_and_list() -> None:
    table = [
        {"Index Name": "NIFTY 50", "HistoricalDate": "03 Nov 1995"}
        | {"OPEN": "-", "HIGH": "-", "LOW": "-", "CLOSE": "1000"},
    ]
    src = object.__new__(NiftyIndicesHistorySource)
    src._http = None  # type: ignore[attr-defined]
    as_string = src._parse(json.dumps({"d": json.dumps(table)}).encode(), index_name="NIFTY 50")
    as_list = src._parse(json.dumps({"d": table}).encode(), index_name="NIFTY 50")
    assert [r.trade_date for r in as_string] == [date(1995, 11, 3)]
    assert as_string[0].close == 1000.0 and as_string[0].open is None
    assert [(r.trade_date, r.close) for r in as_list] == [(r.trade_date, r.close) for r in as_string]


class _StubSource(HistoricalIndexSource):
    name = "stub"

    def __init__(self, rows_by_index: dict[str, list[IndexHistoryRow]]) -> None:
        self._rows = rows_by_index

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes:  # pragma: no cover
        raise AssertionError("stub does not fetch")

    def _parse(self, payload: bytes, *, index_name: str) -> list[IndexHistoryRow]:  # pragma: no cover
        raise AssertionError("stub does not parse")

    def fetch_series(self, index_name: str, from_date: date, to_date: date) -> list[IndexHistoryRow]:
        return [r for r in self._rows.get(index_name, []) if from_date <= r.trade_date <= to_date]


class _BrokenSource(HistoricalIndexSource):
    def __init__(self) -> None:
        pass

    def _fetch_chunk(self, index_name: str, start: date, end: date) -> bytes:  # pragma: no cover
        raise AssertionError("unused")

    def _parse(self, payload: bytes, *, index_name: str) -> list[IndexHistoryRow]:  # pragma: no cover
        raise AssertionError("unused")

    def fetch_series(self, index_name: str, from_date: date, to_date: date) -> list[IndexHistoryRow]:
        raise DownloadError("fallback source is down")


def _row(day: date, name: str, close: float) -> IndexHistoryRow:
    return IndexHistoryRow(trade_date=day, index_name=name, open=close, high=close, low=close, close=close)


def _close_only(day: date, name: str, close: float) -> IndexHistoryRow:
    return IndexHistoryRow(trade_date=day, index_name=name, open=None, high=None, low=None, close=close)


def test_downloader_stages_and_reads_across_names(tmp_path: Path) -> None:
    days = [date(1999, 1, 4), date(1999, 1, 5), date(1999, 1, 6)]
    stub = _StubSource(
        {
            "NIFTY 50": [_row(d, "NIFTY 50", 100 + i) for i, d in enumerate(days)],
            "NIFTY BANK": [_row(d, "NIFTY BANK", 200 + i) for i, d in enumerate(days)],
        }
    )
    dl = IndexHistoryDownloader(tmp_path, sleep_seconds=0, sources=[stub])
    summary = dl.download_range(date(1999, 1, 1), date(1999, 1, 31), ["NIFTY 50", "NIFTY BANK"])
    assert summary.downloaded_count == 6 and summary.failed_count == 0

    path = staged_path(tmp_path, INDEX_CLOSES, days[0])
    text = path.read_text(encoding="utf-8")
    header = "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value"
    assert text.splitlines()[0] == header
    assert "NIFTY 50,04-01-1999" in text and "NIFTY BANK,04-01-1999" in text

    frame = NSEData(tmp_path).index("NIFTY 50").ohlc(from_date=date(1999, 1, 1), to_date=date(1999, 1, 6))
    assert list(frame["trade_date"]) == days
    assert list(frame["close"]) == [100.0, 101.0, 102.0]

    before = path.read_bytes()
    again = dl.download_range(date(1999, 1, 1), date(1999, 1, 31), ["NIFTY 50", "NIFTY BANK"])
    assert again.downloaded_count == 0 and again.skipped_existing_count == 6
    assert path.read_bytes() == before


def test_downloader_merges_into_existing_day_file_keeping_extra_columns(tmp_path: Path) -> None:
    day = date(2013, 6, 3)  # a day the ind_close_all archive already covers
    existing = staged_path(tmp_path, INDEX_CLOSES, day)
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text(
        "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
        "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n"
        "CNX Nifty Junior,03-06-2013,-,-,-,4200.5,10,0.2,123,456.7,18.1,3.2,1.1\n",
        encoding="utf-8",
    )
    stub = _StubSource({"NIFTY 50": [_row(day, "NIFTY 50", 2100.0)]})
    dl = IndexHistoryDownloader(tmp_path, sleep_seconds=0, sources=[stub])
    dl.download_range(day, day, ["NIFTY 50"])
    text = existing.read_text(encoding="utf-8")
    assert "P/E" in text.splitlines()[0] and "Div Yield" in text.splitlines()[0]
    assert ",18.1,3.2,1.1" in text  # the pre-existing row's extra columns survived the merge
    assert "NIFTY 50,03-06-2013" in text


def test_close_only_rows_are_readable(tmp_path: Path) -> None:
    days = [date(1996, 4, 1), date(1996, 4, 2)]
    stub = _StubSource({"NIFTY 50": [_close_only(d, "NIFTY 50", 1050.0 + i) for i, d in enumerate(days)]})
    dl = IndexHistoryDownloader(tmp_path, sleep_seconds=0, sources=[stub])
    dl.download_range(days[0], days[-1], ["NIFTY 50"])
    frame = NSEData(tmp_path).index("NIFTY 50").ohlc(from_date=days[0], to_date=days[-1])
    assert list(frame["trade_date"]) == days
    assert list(frame["close"]) == [1050.0, 1051.0]
    assert list(frame["open"]) == [1050.0, 1051.0]  # O/H/L filled from close so the row survives the parser


def test_fallback_failure_keeps_primary_rows(tmp_path: Path) -> None:
    primary = _StubSource({"NIFTY 50": [_row(date(2005, 1, 3), "NIFTY 50", 2000.0)]})
    dl = IndexHistoryDownloader(tmp_path, sleep_seconds=0, sources=[primary, _BrokenSource()])
    summary = dl.download_range(date(1999, 1, 1), date(2005, 12, 31), ["NIFTY 50"])
    assert summary.failed_count == 0 and summary.downloaded_count == 1
    frame = NSEData(tmp_path).index("NIFTY 50").ohlc(from_date=date(1999, 1, 1), to_date=date(2005, 12, 31))
    assert list(frame["trade_date"]) == [date(2005, 1, 3)]


def test_downloader_stitches_fallback_before_primary(tmp_path: Path) -> None:
    primary = _StubSource({"NIFTY 50": [_row(date(2001, 1, 1), "NIFTY 50", 1300.0)]})
    fallback = _StubSource(
        {"NIFTY 50": [_row(date(1999, 1, 4), "NIFTY 50", 900.0), _row(date(2000, 6, 1), "NIFTY 50", 1100.0)]}
    )
    dl = IndexHistoryDownloader(tmp_path, sleep_seconds=0, sources=[primary, fallback])
    dl.download_range(date(1999, 1, 1), date(2001, 12, 31), ["NIFTY 50"])
    frame = NSEData(tmp_path).index("NIFTY 50").ohlc(from_date=date(1999, 1, 1), to_date=date(2001, 12, 31))
    assert list(frame["trade_date"]) == [date(1999, 1, 4), date(2000, 6, 1), date(2001, 1, 1)]


def test_long_history_names_resolve_to_themselves() -> None:
    for name in LONG_HISTORY_INDEX_NAMES:
        entry = lookup(name)
        assert entry is not None, f"{name!r} not in the bundled index catalog"
        assert entry.name == name
