"""Equity security master (EQUITY_L) typed reads."""

from datetime import date
from pathlib import Path

from support import write_staged

from powernse import NSEData
from powernse.datasets import EQUITY_LIST

_HEADER = "SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\n"


def _master(*rows: str) -> str:
    return _HEADER + "".join(r + "\n" for r in rows)


def test_securities_table_and_lookups(tmp_path: Path) -> None:
    write_staged(
        tmp_path,
        EQUITY_LIST,
        date(2024, 8, 1),
        _master(
            "RELIANCE, Reliance Industries Limited, EQ, 29-NOV-1995, 10, 1, INE002A01018, 10",
            "20MICRONS, 20 Microns Limited, EQ, 06-OCT-2008, 5, 1, INE144J01027, 5",
        ),
    )
    # a later staged file supersedes the earlier one
    write_staged(
        tmp_path,
        EQUITY_LIST,
        date(2024, 8, 8),
        _master(
            "RELIANCE, Reliance Industries Limited, EQ, 29-NOV-1995, 10, 1, INE002A01018, 10",
            "TCS, Tata Consultancy Services Limited, EQ, 25-AUG-2004, 1, 1, INE467B01029, 1",
        ),
    )

    data = NSEData(tmp_path)
    table = data.securities()
    assert list(table["symbol"]) == ["RELIANCE", "TCS"]
    assert table.iloc[0]["isin"] == "INE002A01018"
    assert table.iloc[0]["listing_date"] == date(1995, 11, 29)

    row = data.security("reliance")
    assert row is not None
    assert row["name"] == "Reliance Industries Limited"
    assert row["face_value"] == 10.0

    by_isin = data.security_by_isin("ine467b01029")
    assert by_isin is not None
    assert by_isin["symbol"] == "TCS"

    assert data.security("NOTLISTED") is None
    assert data.security_by_isin("INE000000000") is None


def test_securities_empty_without_staged_file(tmp_path: Path) -> None:
    assert NSEData(tmp_path).securities().empty
