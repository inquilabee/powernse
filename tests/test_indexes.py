"""The bundled index-identity catalog."""

import pytest

from powernse.indexes import IndexEntry, load_entries, lookup

CATEGORIES = {"broad", "sectoral", "thematic", "strategy", "fixed_income"}


def test_catalog_loads_and_is_well_formed() -> None:
    entries = load_entries()
    assert len(entries) > 100
    assert all(isinstance(e, IndexEntry) for e in entries)
    assert all(e.category in CATEGORIES for e in entries)
    assert all(e.name and e.code for e in entries)
    assert entries == tuple(sorted(entries, key=lambda e: e.name))
    assert load_entries() is entries  # cached


@pytest.mark.parametrize(
    ("query", "name", "category", "fno"),
    [
        ("NIFTY 50", "NIFTY 50", "broad", True),
        ("nifty50", "NIFTY 50", "broad", True),
        ("  nifty_50 ", "NIFTY 50", "broad", True),
        ("NIFTY FIN SERVICE", "NIFTY FINANCIAL SERVICES", "broad", True),  # by code
        ("nifty bank", "NIFTY BANK", "broad", True),
        ("NIFTY IT", "NIFTY IT", "sectoral", False),
        ("nifty next 50", "NIFTY NEXT 50", "broad", True),
    ],
)
def test_lookup_normalizes(query: str, name: str, category: str, fno: bool) -> None:
    entry = lookup(query)
    assert entry is not None
    assert (entry.name, entry.category, entry.fno) == (name, category, fno)


def test_lookup_unknown_is_none() -> None:
    assert lookup("Totally Made Up Index") is None
    assert lookup("") is None


def test_exactly_the_fno_broad_indices_are_flagged() -> None:
    fno = {e.name for e in load_entries() if e.fno}
    assert fno == {
        "NIFTY 50",
        "NIFTY NEXT 50",
        "NIFTY BANK",
        "NIFTY FINANCIAL SERVICES",
        "NIFTY MIDCAP SELECT",
        "NIFTY INDIA FPI 150",
    }
