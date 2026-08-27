"""NSEData — read helpers over a local NSE archive root."""

import csv
import json
import logging
from collections.abc import Callable, Iterable, Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import ClassVar, Self

import pandas as pd

from powernse import datasets
from powernse.archive import ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.constants import CA_ADJUSTMENT_LOOKBACK_DAYS
from powernse.downloaders import index_slug, parse_index_constituent_symbols
from powernse.errors import ArchiveError, PayloadError
from powernse.parsers.rows import BhavcopyRow, FoBhavcopyRow, IndexClosesRow
from powernse.schemas import FO_SCHEMA, INDEX_SCHEMA, OHLC_SCHEMA, FoRow, IndexRow, OhlcRow, empty_frame
from powernse.settings import Settings

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
        path = self._archive.staged_path(datasets.BHAVCOPY, trade_date)
        if not path.is_file():
            msg = f"No staged bhavcopy for {trade_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        return path

    def latest_bhavcopy_date(self) -> date | None:
        """Newest staged bhavcopy date under this archive, if any."""
        return self._archive.latest_staged_date(datasets.BHAVCOPY)

    def latest_corporate_actions_date(self) -> date | None:
        """Newest staged corporate-actions date, if any."""
        return self._corporate_actions_bound(prefer_latest=True)

    def earliest_corporate_actions_date(self) -> date | None:
        """Oldest staged corporate-actions date, if any."""
        return self._corporate_actions_bound(prefer_latest=False)

    def _corporate_actions_bound(self, *, prefer_latest: bool) -> date | None:
        bound: date | None = None
        for path in self._archive.list_files(datasets.CORPORATE_ACTIONS.raw_dir):
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

    # Literal-keyed getters so wide_frame()'s dynamic `column` argument stays type-safe
    # (an OhlcRow TypedDict can't be subscripted with a non-literal key).
    _WIDE_FRAME_GETTERS: ClassVar[dict[str, Callable[[OhlcRow], float]]] = {
        "open": lambda row: row["open"],
        "high": lambda row: row["high"],
        "low": lambda row: row["low"],
        "close": lambda row: row["close"],
        "volume": lambda row: row["volume"],
    }

    def _iter_bhavcopy_rows(self, trade_date: date, *, series_needle: str) -> Iterator[OhlcRow]:
        """Parsed, series-filtered OhlcSchema-shaped rows from one staged bhavcopy day, if staged."""
        path = self._archive.staged_path(datasets.BHAVCOPY, trade_date)
        if not path.is_file():
            return
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                bar = BhavcopyRow.from_row(row, trade_date=trade_date)
                if bar is not None and bar["series"] == series_needle:
                    yield bar

    def ohlc(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        """OHLC bars for one symbol across staged bhavcopy days, as an OhlcSchema-shaped DataFrame."""
        start, end = self._resolve_bhavcopy_window(from_date, to_date)
        needle = symbol.strip().upper()
        series_needle = series.strip().upper()
        rows: list[OhlcRow] = []
        for trade_date in iter_trading_dates(start, end):
            for bar in self._iter_bhavcopy_rows(trade_date, series_needle=series_needle):
                if bar["symbol"] == needle:
                    rows.append(bar)
                    break
        if not rows:
            return empty_frame(OHLC_SCHEMA)
        frame = pd.DataFrame(rows, columns=list(OHLC_SCHEMA.columns))
        OHLC_SCHEMA.validate(frame)
        return frame

    def wide_frame(
        self,
        *,
        column: str = "close",
        symbols: Iterable[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        """Date x Symbol wide matrix for one OHLCV column, in a single pass over staged bhavcopy days.

        ``symbols=None`` keeps every symbol seen in the range. Column values
        come straight from the raw (unadjusted) bhavcopy; use
        ``CorporateActions.adjusted_ohlc`` per symbol first if you need
        split/bonus/dividend-adjusted prices.
        """
        key = column.strip().lower()
        getter = self._WIDE_FRAME_GETTERS.get(key)
        if getter is None:
            msg = f"column must be one of {tuple(self._WIDE_FRAME_GETTERS)}, got {column!r}"
            raise ValueError(msg)

        start, end = self._resolve_bhavcopy_window(from_date, to_date)
        series_needle = series.strip().upper()
        wanted = {s.strip().upper() for s in symbols} if symbols is not None else None

        rows: dict[date, dict[str, float]] = {}
        for trade_date in iter_trading_dates(start, end):
            values: dict[str, float] = {}
            for bar in self._iter_bhavcopy_rows(trade_date, series_needle=series_needle):
                if wanted is None or bar["symbol"] in wanted:
                    values[bar["symbol"]] = getter(bar)
            if values:
                rows[trade_date] = values

        frame = pd.DataFrame.from_dict(rows, orient="index").sort_index()
        frame.index.name = "Date"
        return frame

    def latest(self, symbol: str, *, series: str = "EQ") -> pd.Series | None:
        """Most recent staged OHLC bar for a symbol, as a one-row Series, if present."""
        latest_day = self.latest_bhavcopy_date()
        if latest_day is None:
            return None
        frame = self.ohlc(symbol, from_date=latest_day, to_date=latest_day, series=series)
        return frame.iloc[0] if not frame.empty else None

    def ohlc_adjusted(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        """AdjustedOhlcSchema frame: equity OHLC with opt-in bonus/split/dividend adjustments from staged CA files.

        See ``powernse.corporate_actions.CorporateActions`` for the adjustment logic;
        this just wires it to this archive's bars and CA records.
        """
        from powernse.corporate_actions import CorporateActions  # avoid a data<->corporate_actions import cycle

        return CorporateActions(self).adjusted_ohlc(symbol, from_date=from_date, to_date=to_date, series=series)

    def corporate_actions_in_window(
        self,
        symbol: str,
        *,
        window_start: date,
        end: date,
    ) -> list[dict[str, object]]:
        """Corporate-action records for ``symbol`` with an ex-date plausibly in ``[window_start, end]``.

        CA JSON files are selected by filename date in
        ``[window_start - lookback, end]`` (see ``CA_ADJUSTMENT_LOOKBACK_DAYS``) so an
        ex-date inside the window is found even when the file is labeled before
        ``window_start``, without scanning the entire multi-year CA tree day-by-day.
        """
        floor = window_start - timedelta(days=CA_ADJUSTMENT_LOOKBACK_DAYS)
        earliest = self.earliest_corporate_actions_date()
        if earliest is not None and earliest > floor:
            floor = earliest
        needle = symbol.strip().upper()
        matches: list[dict[str, object]] = []
        for path in self._archive.list_files(datasets.CORPORATE_ACTIONS.raw_dir):
            if not path.name.endswith(".json"):
                continue
            try:
                file_day = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if file_day < floor or file_day > end:
                continue
            for record in self.corporate_actions(file_day):
                record_symbol = str(record.get("symbol") or record.get("SYMBOL") or "").upper()
                if record_symbol == needle:
                    matches.append(record)
        return matches

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
    ) -> pd.DataFrame:
        """F&O bars for one underlying across staged F&O bhavcopy days, as an FoSchema-shaped DataFrame."""
        start, end = self._resolve_fo_window(from_date, to_date)
        needle = symbol.strip().upper()
        instrument_needle = instrument_type.strip().upper() if instrument_type else None
        option_needle = option_type.strip().upper() if option_type else None
        rows: list[FoRow] = []
        for trade_date in iter_trading_dates(start, end):
            path = self._archive.staged_path(datasets.FO_BHAVCOPY, trade_date)
            if not path.is_file():
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    bar = FoBhavcopyRow.from_row(row, trade_date=trade_date)
                    if bar is None or bar["symbol"] != needle:
                        continue
                    if instrument_needle is not None and bar["instrument_type"] != instrument_needle:
                        continue
                    if expiry is not None and bar["expiry"] != expiry:
                        continue
                    bar_strike = bar["strike"]
                    if strike is not None and (bar_strike is None or abs(bar_strike - strike) > 1e-9):
                        continue
                    if option_needle is not None and bar["option_type"] != option_needle:
                        continue
                    rows.append(bar)
        if not rows:
            return empty_frame(FO_SCHEMA)
        frame = pd.DataFrame(rows, columns=list(FO_SCHEMA.columns))
        frame["open_interest"] = frame["open_interest"].astype("Int64")
        FO_SCHEMA.validate(frame)
        return frame

    def index_ohlc(
        self,
        index_name: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> pd.DataFrame:
        """OHLC for one index name across staged index-closes files, as an IndexSchema-shaped DataFrame."""
        start, end = self._resolve_index_closes_window(from_date, to_date)
        needle = index_name.strip().casefold()
        rows: list[IndexRow] = []
        for trade_date in iter_trading_dates(start, end):
            path = self._archive.staged_path(datasets.INDEX_CLOSES, trade_date)
            if not path.is_file():
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    bar = IndexClosesRow.from_row(row, trade_date=trade_date)
                    if bar is None:
                        continue
                    if bar["index_name"].casefold() == needle:
                        rows.append(bar)
                        break
        if not rows:
            return empty_frame(INDEX_SCHEMA)
        frame = pd.DataFrame(rows, columns=list(INDEX_SCHEMA.columns))
        INDEX_SCHEMA.validate(frame)
        return frame

    def full_bhavcopy_rows(self, trade_date: date) -> list[dict[str, str]]:
        path = self._archive.staged_path(datasets.FULL_BHAVCOPY, trade_date)
        if not path.is_file():
            msg = f"No staged full bhavcopy for {trade_date.isoformat()} under {self.root}"
            raise ArchiveError(msg)
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def bulk_deals(self, label_date: date) -> list[dict[str, str]]:
        return self._staged_csv_rows(datasets.BULK_DEALS, label_date, "bulk deals")

    def block_deals(self, label_date: date) -> list[dict[str, str]]:
        return self._staged_csv_rows(datasets.BLOCK_DEALS, label_date, "block deals")

    def fo_secban(self, label_date: date) -> list[dict[str, str]]:
        return self._staged_csv_rows(datasets.FO_SECBAN, label_date, "fo secban")

    def _staged_csv_rows(self, dataset: datasets.Dataset, label_date: date, label: str) -> list[dict[str, str]]:
        return self._read_csv_rows(self._archive.staged_path(dataset, label_date), label, label_date)

    def on(self, trade_date: date, *, symbol: str | None = None, series: str = "EQ") -> pd.DataFrame:
        """All (or one) OHLC bars from a single staged bhavcopy day, as an OhlcSchema-shaped DataFrame."""
        self.bhavcopy_path(trade_date)  # raises ArchiveError if the day isn't staged
        series_needle = series.strip().upper()
        symbol_needle = symbol.strip().upper() if symbol else None
        rows = [
            bar
            for bar in self._iter_bhavcopy_rows(trade_date, series_needle=series_needle)
            if symbol_needle is None or bar["symbol"] == symbol_needle
        ]
        if not rows:
            return empty_frame(OHLC_SCHEMA)
        frame = pd.DataFrame(rows, columns=list(OHLC_SCHEMA.columns))
        OHLC_SCHEMA.validate(frame)
        return frame

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
            path = self._archive.staged_path(datasets.CORPORATE_ACTIONS, trade_date)
            if not path.is_file():
                continue
            for record in self.corporate_actions(trade_date):
                record_symbol = str(record.get("symbol") or record.get("SYMBOL") or "").upper()
                if record_symbol == needle:
                    matches.append(record)
        return matches

    def corporate_actions(self, trade_date: date) -> list[dict[str, object]]:
        path = self._archive.staged_path(datasets.CORPORATE_ACTIONS, trade_date)
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
        path = self._archive.staged_path(datasets.INDEX_CONSTITUENTS, trade_date, discriminator=index_slug(index_name))
        if not path.is_file():
            msg = f"No staged index constituents for {index_name!r} on {trade_date.isoformat()}"
            raise ArchiveError(msg)
        return parse_index_constituent_symbols(path.read_bytes())

    def coverage_gaps(self, *, from_date: date | None = None, to_date: date | None = None) -> list[date]:
        """XBOM sessions in the window that have no staged bhavcopy file."""
        start, end = self._resolve_bhavcopy_window(from_date, to_date)
        missing: list[date] = []
        for trade_date in iter_trading_dates(start, end):
            if not self._archive.staged_path(datasets.BHAVCOPY, trade_date).is_file():
                missing.append(trade_date)
        return missing

    def inventory(self) -> dict[str, int]:
        """Return file counts by archive prefix."""
        return {
            "bhavcopy": len(self._archive.list_files(datasets.BHAVCOPY.raw_dir)),
            "fo_bhavcopy": len(self._archive.list_files(datasets.FO_BHAVCOPY.raw_dir)),
            "full_bhavcopy": len(self._archive.list_files(datasets.FULL_BHAVCOPY.raw_dir)),
            "index_closes": len(self._archive.list_files(datasets.INDEX_CLOSES.raw_dir)),
            "bulk_deals": len(self._archive.list_files(datasets.BULK_DEALS.raw_dir)),
            "block_deals": len(self._archive.list_files(datasets.BLOCK_DEALS.raw_dir)),
            "fo_secban": len(self._archive.list_files(datasets.FO_SECBAN.raw_dir)),
            "corporate_actions": len(self._archive.list_files(datasets.CORPORATE_ACTIONS.raw_dir)),
            "index_constituents": len(self._archive.list_files(datasets.INDEX_CONSTITUENTS.raw_dir)),
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
            latest=self._archive.latest_staged_date(datasets.FO_BHAVCOPY),
            empty_message=f"No staged F&O bhavcopy under {self.root}; download data first",
        )

    def _resolve_index_closes_window(self, from_date: date | None, to_date: date | None) -> tuple[date, date]:
        return self._resolve_window(
            from_date,
            to_date,
            latest=self._archive.latest_staged_date(datasets.INDEX_CLOSES),
            empty_message=f"No staged index closes under {self.root}; download data first",
        )

    def latest_full_bhavcopy_date(self) -> date | None:
        return self._archive.latest_staged_date(datasets.FULL_BHAVCOPY)

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
