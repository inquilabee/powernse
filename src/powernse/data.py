"""NSEData — read helpers over a local NSE archive root."""

import csv
import json
import logging
from datetime import date
from pathlib import Path
from typing import Self

import pandas as pd

from powernse.adjust import apply_price_adjustments, corporate_action_price_events
from powernse.archive import (
    RAW_BHAVCOPY_DIR,
    RAW_BLOCK_DEALS_DIR,
    RAW_BULK_DEALS_DIR,
    RAW_CORPORATE_ACTIONS_DIR,
    RAW_FO_BHAVCOPY_DIR,
    RAW_FO_SECBAN_DIR,
    RAW_FULL_BHAVCOPY_DIR,
    RAW_INDEX_CLOSES_DIR,
    RAW_INDEX_CONSTITUENTS_DIR,
    ArchiveRoot,
)
from powernse.calendar import iter_trading_dates
from powernse.downloaders.bhavcopy import latest_staged_bhavcopy_date, staged_bhavcopy_csv_path
from powernse.downloaders.corporate_actions import corporate_actions_staged_path
from powernse.downloaders.deals import (
    staged_block_deals_csv_path,
    staged_bulk_deals_csv_path,
    staged_fo_secban_csv_path,
)
from powernse.downloaders.fo_bhavcopy import latest_staged_fo_bhavcopy_date, staged_fo_bhavcopy_csv_path
from powernse.downloaders.full_bhavcopy import latest_staged_full_bhavcopy_date, staged_full_bhavcopy_csv_path
from powernse.downloaders.index_closes import latest_staged_index_closes_date, staged_index_closes_csv_path
from powernse.downloaders.index_constituents import (
    index_constituents_staged_path,
    parse_index_constituent_symbols,
)
from powernse.errors import ArchiveError, PayloadError
from powernse.parsers.rows import BhavcopyRow, FoBhavcopyRow, IndexClosesRow
from powernse.settings import Settings
from powernse.types import AdjustedOhlcBar, FoBar, IndexBar, OhlcBar

logger = logging.getLogger(__name__)


class NSEData:
    """Lifecycle owner for reading and querying a staged NSE archive."""

    def __init__(self, root: Path | str | ArchiveRoot | None = None, *, create: bool = False) -> None:
        if isinstance(root, ArchiveRoot):
            self._archive = root
        else:
            settings = Settings.resolve(root)
            if create:
                self._archive = ArchiveRoot.open(settings.archive_root)
            else:
                self._archive = ArchiveRoot.connect(settings.archive_root)

    @classmethod
    def open(cls, root: Path | str | None = None, *, create: bool = False) -> Self:
        return cls(root, create=create)

    @property
    def root(self) -> Path:
        return self._archive.root

    def bhavcopy_path(self, trade_date: date) -> Path:
        path = staged_bhavcopy_csv_path(self.root, trade_date)
        if not path.is_file():
            msg = f"No staged bhavcopy for {trade_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        return path

    def latest_bhavcopy_date(self) -> date | None:
        """Newest staged bhavcopy date under this archive, if any."""
        return latest_staged_bhavcopy_date(self._archive)

    def latest_corporate_actions_date(self) -> date | None:
        """Newest staged corporate-actions date, if any."""
        return self._corporate_actions_bound(prefer_latest=True)

    def earliest_corporate_actions_date(self) -> date | None:
        """Oldest staged corporate-actions date, if any."""
        return self._corporate_actions_bound(prefer_latest=False)

    def _corporate_actions_bound(self, *, prefer_latest: bool) -> date | None:
        bound: date | None = None
        for path in self._archive.list_files(RAW_CORPORATE_ACTIONS_DIR):
            if not path.name.endswith(".json"):
                continue
            try:
                candidate = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if bound is None:
                bound = candidate
            elif prefer_latest and candidate > bound:
                bound = candidate
            elif not prefer_latest and candidate < bound:
                bound = candidate
        return bound

    def bhavcopy_rows(self, trade_date: date) -> list[dict[str, str]]:
        path = self.bhavcopy_path(trade_date)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def bhavcopy_frame(self, trade_date: date) -> pd.DataFrame:
        return pd.read_csv(self.bhavcopy_path(trade_date))

    def ohlc(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> list[OhlcBar]:
        """Return OHLC bars for one symbol across staged bhavcopy days."""
        start, end = self._resolve_bhavcopy_window(from_date, to_date)
        needle = symbol.strip().upper()
        series_needle = series.strip().upper()
        bars: list[OhlcBar] = []
        for trade_date in iter_trading_dates(start, end):
            path = staged_bhavcopy_csv_path(self.root, trade_date)
            if not path.is_file():
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    bar = BhavcopyRow.from_row(row, trade_date=trade_date)
                    if bar is None:
                        continue
                    if bar.symbol == needle and bar.series == series_needle:
                        bars.append(bar)
                        break
        return bars

    def ohlc_frame(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        bars = self.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)
        return pd.DataFrame(
            [
                {
                    "trade_date": bar.trade_date,
                    "symbol": bar.symbol,
                    "series": bar.series,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "isin": bar.isin,
                }
                for bar in bars
            ]
        )

    def latest(self, symbol: str, *, series: str = "EQ") -> OhlcBar | None:
        """Most recent staged OHLC bar for a symbol, if present."""
        latest_day = self.latest_bhavcopy_date()
        if latest_day is None:
            return None
        bars = self.ohlc(symbol, from_date=latest_day, to_date=latest_day, series=series)
        return bars[0] if bars else None

    def ohlc_adjusted(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> list[AdjustedOhlcBar]:
        """Return equity OHLC with opt-in bonus/split adjustments from staged CA files.

        Corporate-action JSON is read from the earliest staged CA day through the query
        end date so an ex-date inside the OHLC window is found even when the file is
        labeled before ``from_date``.
        """
        bars = self.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)
        if not bars:
            return []
        end = to_date or bars[-1].trade_date
        window_start = from_date or bars[0].trade_date
        ca_start = self.earliest_corporate_actions_date() or window_start
        if ca_start > end:
            ca_start = window_start
        records = self.actions_for(symbol, from_date=ca_start, to_date=end)
        events = corporate_action_price_events(records)
        return apply_price_adjustments(bars, events)

    def fo_bars(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        instrument_type: str | None = None,
        expiry: date | None = None,
        strike: float | None = None,
        option_type: str | None = None,
    ) -> list[FoBar]:
        """Return F&O bars for one underlying across staged F&O bhavcopy days."""
        start, end = self._resolve_fo_window(from_date, to_date)
        needle = symbol.strip().upper()
        instrument_needle = instrument_type.strip().upper() if instrument_type else None
        option_needle = option_type.strip().upper() if option_type else None
        bars: list[FoBar] = []
        for trade_date in iter_trading_dates(start, end):
            path = staged_fo_bhavcopy_csv_path(self.root, trade_date)
            if not path.is_file():
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    bar = FoBhavcopyRow.from_row(row, trade_date=trade_date)
                    if bar is None or bar.symbol != needle:
                        continue
                    if instrument_needle is not None and bar.instrument_type != instrument_needle:
                        continue
                    if expiry is not None and bar.expiry != expiry:
                        continue
                    if strike is not None and (bar.strike is None or abs(bar.strike - strike) > 1e-9):
                        continue
                    if option_needle is not None and bar.option_type != option_needle:
                        continue
                    bars.append(bar)
        return bars

    def index_ohlc(
        self,
        index_name: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[IndexBar]:
        """Return OHLC for one index name across staged index-closes files."""
        start, end = self._resolve_index_closes_window(from_date, to_date)
        needle = index_name.strip().casefold()
        bars: list[IndexBar] = []
        for trade_date in iter_trading_dates(start, end):
            path = staged_index_closes_csv_path(self.root, trade_date)
            if not path.is_file():
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    bar = IndexClosesRow.from_row(row, trade_date=trade_date)
                    if bar is None:
                        continue
                    if bar.index_name.casefold() == needle:
                        bars.append(bar)
                        break
        return bars

    def full_bhavcopy_rows(self, trade_date: date) -> list[dict[str, str]]:
        path = staged_full_bhavcopy_csv_path(self.root, trade_date)
        if not path.is_file():
            msg = f"No staged full bhavcopy for {trade_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def bulk_deals(self, label_date: date) -> list[dict[str, str]]:
        return self._read_csv_rows(staged_bulk_deals_csv_path(self.root, label_date), "bulk deals", label_date)

    def block_deals(self, label_date: date) -> list[dict[str, str]]:
        return self._read_csv_rows(staged_block_deals_csv_path(self.root, label_date), "block deals", label_date)

    def fo_secban(self, label_date: date) -> list[dict[str, str]]:
        return self._read_csv_rows(staged_fo_secban_csv_path(self.root, label_date), "fo secban", label_date)

    def on(self, trade_date: date, *, symbol: str | None = None, series: str = "EQ") -> list[OhlcBar]:
        """All (or one) OHLC bars from a single staged bhavcopy day."""
        path = self.bhavcopy_path(trade_date)
        series_needle = series.strip().upper()
        symbol_needle = symbol.strip().upper() if symbol else None
        bars: list[OhlcBar] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                bar = BhavcopyRow.from_row(row, trade_date=trade_date)
                if bar is None or bar.series != series_needle:
                    continue
                if symbol_needle is not None and bar.symbol != symbol_needle:
                    continue
                bars.append(bar)
        return bars

    def actions_for(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, object]]:
        """Corporate-action records mentioning ``symbol`` in the staged window."""
        start, end = self._resolve_corporate_actions_window(from_date, to_date)
        needle = symbol.strip().upper()
        matches: list[dict[str, object]] = []
        for trade_date in iter_trading_dates(start, end, all_calendar_days=True):
            path = corporate_actions_staged_path(self.root, trade_date)
            if not path.is_file():
                continue
            for record in self.corporate_actions(trade_date):
                record_symbol = str(record.get("symbol") or record.get("SYMBOL") or "").upper()
                if record_symbol == needle:
                    matches.append(record)
        return matches

    def corporate_actions(self, trade_date: date) -> list[dict[str, object]]:
        path = corporate_actions_staged_path(self.root, trade_date)
        if not path.is_file():
            msg = f"No staged corporate actions for {trade_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        decoded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(decoded, list):
            msg = f"Corporate actions payload must be a JSON list for {trade_date.isoformat()}"
            raise PayloadError(msg)
        records: list[dict[str, object]] = []
        for item in decoded:
            if not isinstance(item, dict):
                msg = "Corporate actions list items must be objects"
                raise PayloadError(msg)
            records.append(item)
        return records

    def index_symbols(self, trade_date: date, index_name: str) -> list[str]:
        path = index_constituents_staged_path(self.root, trade_date, index_name)
        if not path.is_file():
            msg = f"No staged index constituents for {index_name!r} on {trade_date.isoformat()}"
            raise ArchiveError(msg)
        return parse_index_constituent_symbols(path.read_bytes())

    def coverage_gaps(self, *, from_date: date | None = None, to_date: date | None = None) -> list[date]:
        """XBOM sessions in the window that have no staged bhavcopy file."""
        start, end = self._resolve_bhavcopy_window(from_date, to_date)
        missing: list[date] = []
        for trade_date in iter_trading_dates(start, end):
            if not staged_bhavcopy_csv_path(self.root, trade_date).is_file():
                missing.append(trade_date)
        return missing

    def inventory(self) -> dict[str, int]:
        """Return file counts by archive prefix."""
        return {
            "bhavcopy": len(self._archive.list_files(RAW_BHAVCOPY_DIR)),
            "fo_bhavcopy": len(self._archive.list_files(RAW_FO_BHAVCOPY_DIR)),
            "full_bhavcopy": len(self._archive.list_files(RAW_FULL_BHAVCOPY_DIR)),
            "index_closes": len(self._archive.list_files(RAW_INDEX_CLOSES_DIR)),
            "bulk_deals": len(self._archive.list_files(RAW_BULK_DEALS_DIR)),
            "block_deals": len(self._archive.list_files(RAW_BLOCK_DEALS_DIR)),
            "fo_secban": len(self._archive.list_files(RAW_FO_SECBAN_DIR)),
            "corporate_actions": len(self._archive.list_files(RAW_CORPORATE_ACTIONS_DIR)),
            "index_constituents": len(self._archive.list_files(RAW_INDEX_CONSTITUENTS_DIR)),
            "manifest_bytes": self._manifest_bytes(),
        }

    def _manifest_bytes(self) -> int:
        path = self.root / "manifest" / "downloads.jsonl"
        return path.stat().st_size if path.is_file() else 0

    def _read_csv_rows(self, path: Path, label: str, label_date: date) -> list[dict[str, str]]:
        if not path.is_file():
            msg = f"No staged {label} for {label_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _resolve_window(
        self,
        from_date: date | None,
        to_date: date | None,
        *,
        latest: date | None,
        empty_message: str,
    ) -> tuple[date, date]:
        end = to_date or latest
        if end is None:
            raise ArchiveError(empty_message)
        start = from_date or end
        if start > end:
            msg = f"from_date {start} must be on or before to_date {end}"
            raise ValueError(msg)
        return start, end

    def _resolve_bhavcopy_window(self, from_date: date | None, to_date: date | None) -> tuple[date, date]:
        return self._resolve_window(
            from_date,
            to_date,
            latest=self.latest_bhavcopy_date(),
            empty_message=f"No staged bhavcopy under {self.root}; download data first",
        )

    def _resolve_fo_window(self, from_date: date | None, to_date: date | None) -> tuple[date, date]:
        return self._resolve_window(
            from_date,
            to_date,
            latest=latest_staged_fo_bhavcopy_date(self._archive),
            empty_message=f"No staged F&O bhavcopy under {self.root}; download data first",
        )

    def _resolve_index_closes_window(self, from_date: date | None, to_date: date | None) -> tuple[date, date]:
        return self._resolve_window(
            from_date,
            to_date,
            latest=latest_staged_index_closes_date(self._archive),
            empty_message=f"No staged index closes under {self.root}; download data first",
        )

    def latest_full_bhavcopy_date(self) -> date | None:
        return latest_staged_full_bhavcopy_date(self._archive)

    def _resolve_corporate_actions_window(
        self,
        from_date: date | None,
        to_date: date | None,
    ) -> tuple[date, date]:
        if from_date is not None and to_date is not None:
            if from_date > to_date:
                msg = f"from_date {from_date} must be on or before to_date {to_date}"
                raise ValueError(msg)
            return from_date, to_date
        latest = self.latest_corporate_actions_date()
        end = to_date or latest
        if end is None:
            msg = f"No staged corporate actions under {self.root}; download data first or pass --from/--to"
            raise ArchiveError(msg)
        start = from_date or end
        if start > end:
            msg = f"from_date {start} must be on or before to_date {end}"
            raise ValueError(msg)
        return start, end
