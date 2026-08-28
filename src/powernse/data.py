"""NSEData -- the read facade over a local NSE archive.

The published entry point for reading a staged archive: it owns the
:class:`ArchiveRoot` and one reader per data family (:mod:`powernse.reading`,
internal), and its verbs delegate there. ``ohlc_adjusted`` / ``corporate_actions``
additionally compose a reader with
:class:`powernse.corporate_actions.CorporateActions`.
"""

from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Self

import pandas as pd

from powernse.archive import ArchiveRoot
from powernse.corporate_actions import CorporateActions
from powernse.index import Index
from powernse.reading import BhavcopyReader, CorporateActionReader, FoReader, IndexReader, SnapshotReader
from powernse.schemas import ADJUSTED_OHLC_SCHEMA, empty_frame
from powernse.settings import Settings

Record = dict[str, object]


class NSEData:
    """Facade over the staged-archive read subsystem: OHLC, F&O, indices, corporate actions, snapshots."""

    def __init__(self, root: Path | str | ArchiveRoot | None = None, *, create: bool = False) -> None:
        if isinstance(root, ArchiveRoot):
            self._archive = root
        else:
            archive_root = Settings.resolve(root).archive_root
            self._archive = ArchiveRoot.open(archive_root) if create else ArchiveRoot.connect(archive_root)
        self._bhavcopy = BhavcopyReader(self._archive)
        self._fo = FoReader(self._archive)
        self._index = IndexReader(self._archive)
        self._actions = CorporateActionReader(self._archive)
        self._snapshots = SnapshotReader(self._archive)

    @classmethod
    def open(cls, root: Path | str | None = None, *, create: bool = False) -> Self:
        return cls(root, create=create)

    @property
    def root(self) -> Path:
        return self._archive.root

    # -- equity OHLC -----------------------------------------------------------

    def ohlc(
        self, symbol: str, *, from_date: date | None = None, to_date: date | None = None, series: str = "EQ"
    ) -> pd.DataFrame:
        """OHLC bars for one symbol across staged bhavcopy days (OhlcSchema-shaped)."""
        return self._bhavcopy.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)

    def on(self, trade_date: date, *, symbol: str | None = None, series: str = "EQ") -> pd.DataFrame:
        """All (or one) OHLC bars from a single staged bhavcopy day."""
        return self._bhavcopy.on(trade_date, symbol=symbol, series=series)

    def latest(self, symbol: str, *, series: str = "EQ") -> pd.Series | None:
        """Most recent staged OHLC bar for a symbol, as a one-row Series, if present."""
        return self._bhavcopy.latest(symbol, series=series)

    def wide_frame(
        self,
        *,
        column: str = "close",
        symbols: Iterable[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
        adjusted: bool = False,
    ) -> pd.DataFrame:
        """Date x Symbol matrix for one OHLCV column in a single pass over staged bhavcopy days.

        ``adjusted=True`` divides each symbol's column by its cumulative
        bonus/split/dividend factor (newest date == 1.0), the same math as
        ``ohlc_adjusted`` -- only ``column="close"`` is supported for it.
        """
        raw = self._bhavcopy.wide_frame(
            column=column, symbols=symbols, from_date=from_date, to_date=to_date, series=series
        )
        if not adjusted or raw.empty:
            return raw
        if column != "close":
            msg = f"adjusted=True only supports column='close', got {column!r}"
            raise ValueError(msg)
        return self._adjust_matrix(raw)

    def _adjust_matrix(self, raw: pd.DataFrame) -> pd.DataFrame:
        start, end = raw.index[0], raw.index[-1]
        out = raw.copy()
        for symbol in raw.columns:
            col = raw[symbol].dropna()
            if col.empty:
                continue
            records = self._actions.records_in_adjustment_window(str(symbol), window_start=start, end=end)
            if not records:
                continue
            bars = pd.DataFrame({"trade_date": list(col.index), "close": col.to_numpy()})
            factors = CorporateActions(records).factors(bars).reindex(raw.index)
            out[symbol] = raw[symbol] / factors
        return out

    def coverage_gaps(self, *, from_date: date | None = None, to_date: date | None = None) -> list[date]:
        """XBOM sessions in the window that have no staged bhavcopy file."""
        return self._bhavcopy.coverage_gaps(from_date=from_date, to_date=to_date)

    def bhavcopy_path(self, trade_date: date) -> Path:
        return self._bhavcopy.staged_path(trade_date)

    def latest_bhavcopy_date(self) -> date | None:
        return self._bhavcopy.latest_date()

    # -- F&O and indices -----------------------------------------------------

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
        """F&O bars for one underlying across staged F&O bhavcopy days (FoSchema-shaped)."""
        return self._fo.fo_bars(
            symbol,
            from_date=from_date,
            to_date=to_date,
            instrument_type=instrument_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )

    def indexes(self, on: date | None = None) -> list[str]:
        """Index names present in the staged index-closes file for ``on`` (default: latest day)."""
        return self._index.names(on=on)

    def index(self, name: str) -> Index:
        """A handle to one index: ``.ohlc()`` / ``.latest()`` / ``.symbols(on)`` / ``.constituent_dates()``."""
        return Index(name, self._index)

    # -- corporate actions -------------------------------------------------

    def corporate_actions(
        self, symbol: str, *, from_date: date | None = None, to_date: date | None = None
    ) -> pd.DataFrame:
        """Classified CA history for a symbol: type / subject / price_factor / dividend_amount per ex-date."""
        records = self._actions.records(symbol, from_date=from_date, to_date=to_date)
        return CorporateActions(records).classified()

    def actions_for(self, symbol: str, *, from_date: date | None = None, to_date: date | None = None) -> list[Record]:
        """Unclassified CA records mentioning ``symbol`` across the staged window (escape hatch)."""
        return self._actions.records(symbol, from_date=from_date, to_date=to_date)

    def ohlc_adjusted(
        self, symbol: str, *, from_date: date | None = None, to_date: date | None = None, series: str = "EQ"
    ) -> pd.DataFrame:
        """Equity OHLC with opt-in bonus/split/dividend adjustments (AdjustedOhlcSchema-shaped)."""
        bars = self._bhavcopy.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)
        if bars.empty:
            return empty_frame(ADJUSTED_OHLC_SCHEMA)
        window_start = from_date or bars["trade_date"].min()
        end = to_date or bars["trade_date"].max()
        records = self._actions.records_in_adjustment_window(symbol, window_start=window_start, end=end)
        return CorporateActions(records).adjust(bars)

    # -- snapshots + inventory ----------------------------------------------

    def full_bhavcopy_rows(self, trade_date: date) -> list[dict[str, str]]:
        return self._snapshots.full_bhavcopy_rows(trade_date)

    def bulk_deals(self, label_date: date) -> list[dict[str, str]]:
        return self._snapshots.bulk_deals(label_date)

    def block_deals(self, label_date: date) -> list[dict[str, str]]:
        return self._snapshots.block_deals(label_date)

    def fo_secban(self, label_date: date) -> list[dict[str, str]]:
        return self._snapshots.fo_secban(label_date)

    def inventory(self) -> dict[str, int]:
        """Staged file counts by dataset, plus the manifest byte size."""
        return self._snapshots.inventory()
