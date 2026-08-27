"""NSEData -- the read facade over a local NSE archive.

Thin: it owns the :class:`ArchiveRoot` and a reader per data family
(:mod:`powernse.reading`), and delegates. The only real logic here is
``ohlc_adjusted`` / ``corporate_actions``, which compose a reader with
:class:`powernse.corporate_actions.CorporateActions`.
"""

from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Self

import pandas as pd

from powernse.archive import ArchiveRoot
from powernse.reading import BhavcopyReader, CorporateActionReader, FoReader, IndexReader, SnapshotReader
from powernse.settings import Settings

Record = dict[str, object]


class NSEData:
    """Read and query a staged NSE archive: OHLC, F&O, indices, corporate actions, snapshots."""

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
    ) -> pd.DataFrame:
        """Date x Symbol matrix for one OHLCV column in a single pass over staged bhavcopy days.

        Values are raw (unadjusted) bhavcopy; run ``ohlc_adjusted`` per symbol
        first if you need split/bonus/dividend-adjusted prices.
        """
        return self._bhavcopy.wide_frame(
            column=column, symbols=symbols, from_date=from_date, to_date=to_date, series=series
        )

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

    def index_ohlc(
        self, index_name: str, *, from_date: date | None = None, to_date: date | None = None
    ) -> pd.DataFrame:
        """OHLC for one index name across staged index-closes files (IndexSchema-shaped)."""
        return self._index.index_ohlc(index_name, from_date=from_date, to_date=to_date)

    def index_symbols(self, trade_date: date, index_name: str) -> list[str]:
        """EQ-series constituent symbols for an index on a staged snapshot date."""
        return self._index.index_symbols(trade_date, index_name)

    # -- corporate actions -------------------------------------------------

    def corporate_actions(self, trade_date: date) -> list[Record]:
        """Raw CA records from one staged JSON file."""
        return self._actions.raw(trade_date)

    def actions_for(self, symbol: str, *, from_date: date | None = None, to_date: date | None = None) -> list[Record]:
        """Raw CA records mentioning ``symbol`` across the staged window."""
        return self._actions.records(symbol, from_date=from_date, to_date=to_date)

    def corporate_actions_in_window(self, symbol: str, *, window_start: date, end: date) -> list[Record]:
        """Raw CA records for ``symbol`` with a label date near ``[window_start, end]``."""
        return self._actions.records_in_adjustment_window(symbol, window_start=window_start, end=end)

    def ohlc_adjusted(
        self, symbol: str, *, from_date: date | None = None, to_date: date | None = None, series: str = "EQ"
    ) -> pd.DataFrame:
        """Equity OHLC with opt-in bonus/split/dividend adjustments (AdjustedOhlcSchema-shaped)."""
        from powernse.corporate_actions import CorporateActions  # avoid a data<->corporate_actions cycle

        return CorporateActions(self).adjusted_ohlc(symbol, from_date=from_date, to_date=to_date, series=series)

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
