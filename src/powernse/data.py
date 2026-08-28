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
from powernse.datasets import BHAVCOPY, BLOCK_DEALS, BULK_DEALS, Dataset
from powernse.index import Index
from powernse.reading import (
    BhavcopyReader,
    CorporateActionReader,
    CoverageReader,
    DealsReader,
    DeliveryReader,
    FoReader,
    IndexReader,
    SecbanReader,
    SnapshotReader,
)
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
        self._delivery = DeliveryReader(self._archive)
        self._fo = FoReader(self._archive)
        self._index = IndexReader(self._archive)
        self._actions = CorporateActionReader(self._archive)
        self._coverage = CoverageReader(self._archive)
        self._bulk_deals = DealsReader(self._archive, BULK_DEALS, "bulk deals")
        self._block_deals = DealsReader(self._archive, BLOCK_DEALS, "block deals")
        self._secban = SecbanReader(self._archive)
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

    def coverage(self, dataset: Dataset, *, from_date: date | None = None, to_date: date | None = None) -> list[date]:
        """XBOM sessions with no staged ``dataset`` file. Window defaults to that dataset's staged span."""
        return self._coverage.missing(dataset, from_date=from_date, to_date=to_date)

    def coverage_gaps(self, *, from_date: date | None = None, to_date: date | None = None) -> list[date]:
        """XBOM sessions that have no staged bhavcopy file (``coverage(BHAVCOPY, ...)``)."""
        return self._coverage.missing(BHAVCOPY, from_date=from_date, to_date=to_date)

    # -- delivery / traded value -----------------------------------------------

    def delivery(
        self, symbol: str, *, from_date: date | None = None, to_date: date | None = None, series: str = "EQ"
    ) -> pd.DataFrame:
        """Delivery qty/%, turnover, and trade count for one symbol (DeliverySchema-shaped)."""
        return self._delivery.delivery(symbol, from_date=from_date, to_date=to_date, series=series)

    def delivery_on(self, trade_date: date, *, symbol: str | None = None, series: str | None = "EQ") -> pd.DataFrame:
        """All (or one symbol / one series) delivery rows from a single staged full-bhavcopy day."""
        return self._delivery.on(trade_date, symbol=symbol, series=series)

    def delivery_frame(
        self,
        *,
        column: str = "delivery_pct",
        symbols: Iterable[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> pd.DataFrame:
        """Date x Symbol matrix of one delivery column (delivery_pct / delivery_qty / turnover_lacs / volume)."""
        return self._delivery.wide_frame(
            column=column, symbols=symbols, from_date=from_date, to_date=to_date, series=series
        )

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

    # -- deals + F&O ban --------------------------------------------------------

    def bulk_deals(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        symbol: str | None = None,
        side: str | None = None,
    ) -> pd.DataFrame:
        """Bulk deals across the staged window (DealSchema-shaped); filter by ``symbol`` / ``side``."""
        return self._bulk_deals.deals(from_date=from_date, to_date=to_date, symbol=symbol, side=side)

    def block_deals(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        symbol: str | None = None,
        side: str | None = None,
    ) -> pd.DataFrame:
        """Block deals across the staged window (DealSchema-shaped); filter by ``symbol`` / ``side``."""
        return self._block_deals.deals(from_date=from_date, to_date=to_date, symbol=symbol, side=side)

    def secban(self, on: date | None = None) -> set[str]:
        """Symbols in the F&O trade ban for ``on`` (default: the latest staged ban date)."""
        return self._secban.banned(on)

    def is_banned(self, symbol: str, on: date | None = None) -> bool:
        """Whether ``symbol`` is in the F&O trade ban for ``on`` (default: latest staged ban date)."""
        return symbol.strip().upper() in self._secban.banned(on)

    # -- snapshots + inventory ----------------------------------------------

    def full_bhavcopy_rows(self, trade_date: date) -> list[dict[str, str]]:
        return self._snapshots.full_bhavcopy_rows(trade_date)

    def inventory(self) -> dict[str, int]:
        """Staged file counts by dataset, plus the manifest byte size."""
        return self._snapshots.inventory()
