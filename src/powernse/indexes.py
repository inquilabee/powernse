"""The bundled catalog of NSE equity indexes (identity only, not membership).

Generated from NSE's ``/api/allIndices`` by ``scripts/build_index_catalog.py``.
Membership (constituents) changes with every rebalance and stays archive-backed.
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Literal

Category = Literal["broad", "sectoral", "thematic", "strategy", "fixed_income"]


def _key(text: str) -> str:
    """Fold a name/code to a match key: lowercase, alphanumerics only ('NIFTY 50' -> 'nifty50')."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """One NSE index's identity: canonical name, short code, and classification."""

    name: str
    code: str
    category: Category
    fno: bool


@cache
def load_entries() -> tuple[IndexEntry, ...]:
    """Every catalogued index, sorted by name (parsed once, then cached)."""
    raw = json.loads(files("powernse.resources").joinpath("indexes.json").read_text(encoding="utf-8"))
    return tuple(IndexEntry(**item) for item in raw)


@cache
def _by_key() -> dict[str, IndexEntry]:
    table: dict[str, IndexEntry] = {}
    for entry in load_entries():
        table.setdefault(_key(entry.name), entry)
        table.setdefault(_key(entry.code), entry)
    return table


def lookup(name: str) -> IndexEntry | None:
    """The catalogued index matching ``name`` by name or code, or ``None``.

    Case- and separator-insensitive: ``"NIFTY 50"`` / ``"nifty50"`` /
    ``"nifty_50"`` all resolve; so does the short code (``"NIFTY FIN SERVICE"``).
    """
    return _by_key().get(_key(name))
