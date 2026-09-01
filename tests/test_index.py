"""The Index handle: list, OHLC, latest, constituents, snapshot dates."""

import json
from datetime import date
from pathlib import Path

import pytest
from support import staged_path

from powernse import Index, NSEData
from powernse.datasets import INDEX_CLOSES, INDEX_CONSTITUENTS
from powernse.downloaders import index_slug
from powernse.errors import ArchiveError

_CLOSES = (
    "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value\n"
    "Nifty 50,{d},100,110,90,105\n"
    "Nifty 500,{d},200,210,190,205\n"
)


def _stage_closes(root: Path, day: date) -> None:
    p = staged_path(root, INDEX_CLOSES, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_CLOSES.format(d=day.strftime("%d-%m-%Y")), encoding="utf-8")


def _stage_named_close(root: Path, day: date, index_name: str, close: float) -> None:
    p = staged_path(root, INDEX_CLOSES, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    header = "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value\n"
    p.write_text(f"{header}{index_name},{day.strftime('%d-%m-%Y')},{close},{close},{close},{close}\n", encoding="utf-8")


def _stage_constituents(root: Path, day: date, name: str, symbols: list[str]) -> None:
    p = staged_path(root, INDEX_CONSTITUENTS, day, discriminator=index_slug(name))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"data": [{"symbol": s, "series": "EQ"} for s in symbols]}), encoding="utf-8")


def test_index_standalone_identity() -> None:
    nifty = Index("nifty50")
    assert (nifty.name, nifty.code, nifty.category, nifty.fno, nifty.known) == (
        "NIFTY 50",
        "NIFTY 50",
        "broad",
        True,
        True,
    )
    assert repr(nifty) == "Index('NIFTY 50')"
    assert Index("NIFTY FIN SERVICE").name == "NIFTY FINANCIAL SERVICES"  # by code

    unknown = Index("My Custom Basket")
    assert (unknown.known, unknown.name, unknown.code, unknown.category, unknown.fno) == (
        False,
        "My Custom Basket",
        None,
        None,
        False,
    )
    assert unknown.exists() is False
    assert Index("nifty it").exists() is True  # catalogued, no archive needed


def test_index_standalone_data_ops_need_an_archive() -> None:
    with pytest.raises(ArchiveError, match="not bound to an archive"):
        Index("NIFTY 50").ohlc()
    with pytest.raises(ArchiveError, match="not bound"):
        Index("NIFTY 50").symbols(date(2024, 1, 1))


def test_index_catalog() -> None:
    cat = Index.catalog()
    assert len(cat) > 100
    assert all(isinstance(i, Index) and i.known for i in cat)
    assert "NIFTY 50" in {i.name for i in cat}
    assert {i.category for i in cat} <= {"broad", "sectoral", "thematic", "strategy", "fixed_income"}


def test_indexes_lists_staged_names(tmp_path: Path) -> None:
    _stage_closes(tmp_path, date(2024, 8, 1))
    _stage_closes(tmp_path, date(2024, 8, 2))
    assert NSEData(tmp_path).indexes() == ["Nifty 50", "Nifty 500"]
    assert NSEData(tmp_path).indexes() == NSEData(tmp_path).indexes(on=date(2024, 8, 1))
    assert NSEData(tmp_path).indexes(on=date(2020, 1, 1)) == []


def test_indexes_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from powernse.cli import main

    _stage_closes(tmp_path, date(2024, 8, 1))
    assert main(["indexes", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.split() == ["Nifty", "50", "Nifty", "500"]
    assert main(["indexes", "--root", str(tmp_path / "empty")]) == 1


def test_indexes_cli_known_needs_no_archive(capsys: pytest.CaptureFixture[str]) -> None:
    from powernse.cli import main
    from powernse.index import load_entries

    assert main(["indexes", "--known", "--root", "/no/such/archive"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(load_entries())
    assert any(line.startswith("NIFTY 50\tbroad\tfno") for line in lines)


def test_index_handle_ohlc_latest_exists(tmp_path: Path) -> None:
    _stage_closes(tmp_path, date(2024, 8, 1))
    _stage_closes(tmp_path, date(2024, 8, 2))
    idx = NSEData(tmp_path).index("nifty 50")  # case-insensitive
    assert isinstance(idx, Index)

    ohlc = idx.ohlc(from_date=date(2024, 8, 1), to_date=date(2024, 8, 2))
    assert len(ohlc) == 2
    assert list(ohlc["close"]) == [105.0, 105.0]

    latest = idx.latest()
    assert latest is not None
    assert latest["trade_date"] == date(2024, 8, 2)

    assert idx.exists() is True
    assert NSEData(tmp_path).index("Nifty 999").exists() is False


def test_index_ohlc_stitches_historical_name_aliases(tmp_path: Path) -> None:
    # NSE's staged files carry whichever name was current on that date.
    _stage_named_close(tmp_path, date(2012, 2, 21), "S&P CNX Nifty", 5607.15)
    _stage_named_close(tmp_path, date(2014, 2, 21), "CNX Nifty", 6091.45)
    _stage_named_close(tmp_path, date(2024, 2, 21), "Nifty 50", 22055.05)

    data = NSEData(tmp_path)

    # asked for the present-day name -> the continuous series, not just the post-rename tail
    canonical = data.index("NIFTY 50").ohlc(from_date=date(2012, 1, 1), to_date=date(2025, 1, 1))
    assert list(canonical["close"]) == [5607.15, 6091.45, 22055.05]

    # an old name resolves to the same index and returns the same continuous series
    old = data.index("CNX Nifty")
    assert (old.known, old.name) == (True, "NIFTY 50")
    assert "CNX Nifty" in old.aliases
    assert list(old.ohlc(from_date=date(2012, 1, 1), to_date=date(2025, 1, 1))["close"]) == [
        5607.15,
        6091.45,
        22055.05,
    ]

    latest = data.index("nifty 50").latest()
    assert latest is not None and latest["trade_date"] == date(2024, 2, 21)


def test_catalog_every_canonical_name_resolves_to_itself() -> None:
    from powernse.index import load_entries, lookup

    for entry in load_entries():
        assert lookup(entry.name) is entry  # an alias key never shadows a real name


def test_every_historical_alias_resolves_to_its_index() -> None:
    from powernse.index import lookup
    from powernse.index.aliases import INDEX_ALIASES

    for canonical, old_names in INDEX_ALIASES.items():
        for old in old_names:
            entry = lookup(old)
            assert entry is not None and entry.name == canonical, f"{old!r} does not resolve to {canonical!r}"


def test_index_handle_constituents(tmp_path: Path) -> None:
    _stage_closes(tmp_path, date(2024, 8, 1))
    _stage_constituents(tmp_path, date(2024, 8, 1), "Nifty 50", ["RELIANCE", "TCS"])
    _stage_constituents(tmp_path, date(2024, 8, 5), "Nifty 50", ["RELIANCE", "INFY"])

    idx = NSEData(tmp_path).index("Nifty 50")
    assert idx.symbols(date(2024, 8, 5)) == ["RELIANCE", "INFY"]
    assert idx.constituent_dates() == [date(2024, 8, 1), date(2024, 8, 5)]

    with pytest.raises(ArchiveError, match="index constituents"):
        idx.symbols(date(2020, 1, 1))
