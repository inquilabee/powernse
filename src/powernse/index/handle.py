"""``Index`` -- a handle to one NSE index: catalog identity + archive-bound data."""

from datetime import date
from typing import Self

import pandas as pd

from powernse.errors import ArchiveError
from powernse.index.catalog import Category, load_entries, lookup
from powernse.reading.index import IndexReader


class Index:
    """A handle to one NSE index.

    ``Index("nifty50")`` on its own carries identity from the bundled catalog
    (``name`` / ``code`` / ``category`` / ``fno`` / ``known``). Data reads
    (``ohlc`` / ``latest`` / ``symbols`` / ``constituent_dates``) need an archive
    -- use ``NSEData(root).index(name)``, which binds a reader.
    """

    def __init__(self, name: str, reader: IndexReader | None = None) -> None:
        entry = lookup(name)
        self._entry = entry
        self._reader = reader
        self.name: str = entry.name if entry else name.strip()
        self.code: str | None = entry.code if entry else None
        self.category: Category | None = entry.category if entry else None
        self.fno: bool = entry.fno if entry else False
        self.aliases: tuple[str, ...] = entry.aliases if entry else ()

    def __repr__(self) -> str:
        return f"Index({self.name!r})"

    @property
    def known(self) -> bool:
        """True when this name resolves to a catalogued NSE index."""
        return self._entry is not None

    @classmethod
    def catalog(cls) -> list[Self]:
        """Every catalogued index, as unbound handles."""
        return [cls(entry.name) for entry in load_entries()]

    def _bound(self) -> IndexReader:
        if self._reader is None:
            msg = f"Index({self.name!r}) is not bound to an archive; use NSEData(root).index({self.name!r})"
            raise ArchiveError(msg)
        return self._reader

    def ohlc(self, *, from_date: date | None = None, to_date: date | None = None) -> pd.DataFrame:
        """OHLC across staged index-closes files (IndexSchema-shaped).

        Rows staged under a former NSE name for this index (``self.aliases``) are
        included, so a query for the present-day name returns the continuous series.
        """
        return self._bound().ohlc(self.name, aliases=self.aliases, from_date=from_date, to_date=to_date)

    def latest(self) -> pd.Series | None:
        """Most recent staged close row, or ``None`` if this index has no staged data."""
        return self._bound().latest_row(self.name, aliases=self.aliases)

    def symbols(self, on: date) -> list[str]:
        """EQ-series constituent symbols from the staged snapshot labelled ``on``."""
        return self._bound().symbols(on, self.name)

    def constituent_dates(self) -> list[date]:
        """Dates for which a constituent snapshot of this index is staged."""
        return self._bound().constituent_dates(self.name)

    def exists(self) -> bool:
        """True when this is a catalogued NSE index, or (if bound) appears in the latest staged file."""
        if self.known:
            return True
        needle = self.name.strip().casefold()
        return self._reader is not None and any(needle == n.casefold() for n in self._reader.names())
