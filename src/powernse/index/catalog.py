"""The bundled catalog of NSE equity indexes -- identity only, not membership.

Generated from NSE's ``/api/allIndices`` by ``scripts/build_index_catalog.py``.
Membership (constituents) changes with every rebalance and stays archive-backed.
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Literal, Self

Category = Literal["broad", "sectoral", "thematic", "strategy", "fixed_income"]


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """One NSE index's identity: canonical name, short code, and classification."""

    name: str
    code: str
    category: Category
    fno: bool


class IndexCatalog:
    """Every catalogued NSE index, with name/code lookup folded to a match key."""

    def __init__(self, entries: tuple[IndexEntry, ...]) -> None:
        self._entries = entries
        self._by_key: dict[str, IndexEntry] = {}
        for entry in entries:
            self._by_key.setdefault(self._key(entry.name), entry)
            self._by_key.setdefault(self._key(entry.code), entry)

    @classmethod
    @cache
    def load(cls) -> Self:
        """The bundled catalog (parsed once, then cached)."""
        raw = json.loads(files("powernse.index.resources").joinpath("indexes.json").read_text(encoding="utf-8"))
        return cls(tuple(IndexEntry(**item) for item in raw))

    def all(self) -> tuple[IndexEntry, ...]:
        return self._entries

    def get(self, name: str) -> IndexEntry | None:
        """The entry matching ``name`` by name or code, or ``None``.

        Case- and separator-insensitive: ``"NIFTY 50"`` / ``"nifty50"`` /
        ``"nifty_50"`` all resolve, and so does the short code.
        """
        return self._by_key.get(self._key(name))

    @staticmethod
    def _key(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", text.lower())


def load_entries() -> tuple[IndexEntry, ...]:
    """Every catalogued index, sorted by name."""
    return IndexCatalog.load().all()


def lookup(name: str) -> IndexEntry | None:
    """The catalogued index matching ``name`` (by name or short code), or ``None``."""
    return IndexCatalog.load().get(name)
