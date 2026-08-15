"""NSEData — read helpers over a local NSE archive root."""

import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Self

from powernse.archive import RAW_BHAVCOPY_DIR, ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.downloaders.bhavcopy import latest_staged_bhavcopy_date, staged_bhavcopy_csv_path
from powernse.downloaders.corporate_actions import corporate_actions_staged_path
from powernse.downloaders.index_constituents import (
    index_constituents_staged_path,
    parse_index_constituent_symbols,
)
from powernse.errors import ArchiveError, PayloadError
from powernse.settings import Settings
from powernse.types import OhlcBar

if TYPE_CHECKING:
    from pandas import DataFrame

_SYMBOL_KEYS = ("SYMBOL", "TckrSymb")
_SERIES_KEYS = ("SERIES", "SctySrs")
_OPEN_KEYS = ("OPEN", "OpnPric")
_HIGH_KEYS = ("HIGH", "HghPric")
_LOW_KEYS = ("LOW", "LwPric")
_CLOSE_KEYS = ("CLOSE", "ClsPric")
_VOLUME_KEYS = ("TOTTRDQTY", "TtlTradgVol")
_ISIN_KEYS = ("ISIN",)
_DATE_KEYS = ("TradDt", "TIMESTAMP")


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

    def bhavcopy_rows(self, trade_date: date) -> list[dict[str, str]]:
        path = self.bhavcopy_path(trade_date)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def bhavcopy_frame(self, trade_date: date) -> "DataFrame":
        try:
            import pandas as pd
        except ImportError as exc:
            msg = "pandas is required for bhavcopy_frame(); install with: pip install powernse[pandas]"
            raise ImportError(msg) from exc
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
        start, end = self._resolve_query_window(from_date, to_date)
        needle = symbol.strip().upper()
        series_needle = series.strip().upper()
        bars: list[OhlcBar] = []
        for trade_date in iter_trading_dates(start, end):
            path = staged_bhavcopy_csv_path(self.root, trade_date)
            if not path.is_file():
                continue
            for row in self.bhavcopy_rows(trade_date):
                bar = self._row_to_ohlc(row, trade_date=trade_date)
                if bar is None:
                    continue
                if bar.symbol == needle and bar.series == series_needle:
                    bars.append(bar)
        return bars

    def ohlc_frame(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> "DataFrame":
        try:
            import pandas as pd
        except ImportError as exc:
            msg = "pandas is required for ohlc_frame(); install with: pip install powernse[pandas]"
            raise ImportError(msg) from exc
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

    def on(self, trade_date: date, *, symbol: str | None = None, series: str = "EQ") -> list[OhlcBar]:
        """All (or one) OHLC bars from a single staged bhavcopy day."""
        rows = self.bhavcopy_rows(trade_date)
        series_needle = series.strip().upper()
        symbol_needle = symbol.strip().upper() if symbol else None
        bars: list[OhlcBar] = []
        for row in rows:
            bar = self._row_to_ohlc(row, trade_date=trade_date)
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
        start, end = self._resolve_query_window(from_date, to_date)
        needle = symbol.strip().upper()
        matches: list[dict[str, object]] = []
        current = start
        while current <= end:
            path = corporate_actions_staged_path(self.root, current)
            if path.is_file():
                for record in self.corporate_actions(current):
                    record_symbol = str(record.get("symbol") or record.get("SYMBOL") or "").upper()
                    if record_symbol == needle:
                        matches.append(record)
            current += timedelta(days=1)
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
        start, end = self._resolve_query_window(from_date, to_date)
        missing: list[date] = []
        for trade_date in iter_trading_dates(start, end):
            if not staged_bhavcopy_csv_path(self.root, trade_date).is_file():
                missing.append(trade_date)
        return missing

    def inventory(self) -> dict[str, int]:
        """Return file counts by archive prefix."""
        return {
            "bhavcopy": len(self._archive.list_files(RAW_BHAVCOPY_DIR)),
            "corporate_actions": len(self._archive.list_files("raw/corporate_actions")),
            "index_constituents": len(self._archive.list_files("raw/index_constituents")),
            "manifest_bytes": self._manifest_bytes(),
        }

    def _manifest_bytes(self) -> int:
        path = self.root / "manifest" / "downloads.jsonl"
        return path.stat().st_size if path.is_file() else 0

    def _resolve_query_window(self, from_date: date | None, to_date: date | None) -> tuple[date, date]:
        latest = self.latest_bhavcopy_date()
        end = to_date or latest
        if end is None:
            msg = f"No staged bhavcopy under {self.root}; download data first"
            raise ArchiveError(msg)
        start = from_date or end
        if start > end:
            msg = f"from_date {start} must be on or before to_date {end}"
            raise ValueError(msg)
        return start, end

    @classmethod
    def _row_to_ohlc(cls, row: dict[str, str], *, trade_date: date) -> OhlcBar | None:
        symbol = cls._first(row, _SYMBOL_KEYS)
        series = cls._first(row, _SERIES_KEYS)
        open_ = cls._first(row, _OPEN_KEYS)
        high = cls._first(row, _HIGH_KEYS)
        low = cls._first(row, _LOW_KEYS)
        close = cls._first(row, _CLOSE_KEYS)
        volume = cls._first(row, _VOLUME_KEYS)
        if None in (symbol, series, open_, high, low, close, volume):
            return None
        isin = cls._first(row, _ISIN_KEYS)
        row_date = cls._parse_row_date(row) or trade_date
        return OhlcBar(
            trade_date=row_date,
            symbol=symbol.strip().upper(),
            series=series.strip().upper(),
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=int(float(volume)),
            isin=isin.strip() if isin else None,
        )

    @staticmethod
    def _first(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip() != "":
                return str(value)
        return None

    @classmethod
    def _parse_row_date(cls, row: dict[str, str]) -> date | None:
        raw = cls._first(row, _DATE_KEYS)
        if raw is None:
            return None
        text = raw.strip()
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
        # Legacy TIMESTAMP like 02-JAN-2024
        for fmt in ("%d-%b-%Y", "%d-%b-%y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None
