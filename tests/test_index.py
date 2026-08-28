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


def _stage_constituents(root: Path, day: date, name: str, symbols: list[str]) -> None:
    p = staged_path(root, INDEX_CONSTITUENTS, day, discriminator=index_slug(name))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"data": [{"symbol": s, "series": "EQ"} for s in symbols]}), encoding="utf-8")


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


def test_index_handle_constituents(tmp_path: Path) -> None:
    _stage_closes(tmp_path, date(2024, 8, 1))
    _stage_constituents(tmp_path, date(2024, 8, 1), "Nifty 50", ["RELIANCE", "TCS"])
    _stage_constituents(tmp_path, date(2024, 8, 5), "Nifty 50", ["RELIANCE", "INFY"])

    idx = NSEData(tmp_path).index("Nifty 50")
    assert idx.symbols(date(2024, 8, 5)) == ["RELIANCE", "INFY"]
    assert idx.constituent_dates() == [date(2024, 8, 1), date(2024, 8, 5)]

    with pytest.raises(ArchiveError, match="index constituents"):
        idx.symbols(date(2020, 1, 1))
