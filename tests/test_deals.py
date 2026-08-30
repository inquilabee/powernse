"""Typed bulk / block deal reads and the F&O securities-in-ban snapshot."""

from datetime import date
from pathlib import Path

from support import write_staged

from powernse import NSEData
from powernse.datasets import BLOCK_DEALS, BULK_DEALS, FO_SECBAN
from powernse.parsers.secban import parse_secban

_BULK_HEADER = "Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price / Wght. Avg. Price,Remarks\n"
_BLOCK_HEADER = "Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price / Wght. Avg. Price\n"


def test_bulk_deals_range_and_filters(tmp_path: Path) -> None:
    write_staged(
        tmp_path,
        BULK_DEALS,
        date(2024, 8, 1),
        _BULK_HEADER
        + "01-AUG-2024,RELIANCE,Reliance Industries,ABC FUND,BUY,81000,2850.50,-\n"
        + "01-AUG-2024,TCS,Tata Consultancy,XYZ LLP,SELL,1234567,3900.00,-\n",
    )
    write_staged(
        tmp_path,
        BULK_DEALS,
        date(2024, 8, 2),
        _BULK_HEADER + "02-AUG-2024,RELIANCE,Reliance Industries,DEF PMS,SELL,5000,2900.00,-\n",
    )

    data = NSEData(tmp_path)
    every = data.bulk_deals(from_date=date(2024, 8, 1), to_date=date(2024, 8, 2))
    assert list(every["trade_date"]) == [date(2024, 8, 1), date(2024, 8, 1), date(2024, 8, 2)]
    assert every.iloc[0]["quantity"] == 81000
    assert every.iloc[0]["price"] == 2850.5

    reliance = data.bulk_deals(symbol="reliance", from_date=date(2024, 8, 1), to_date=date(2024, 8, 2))
    assert set(reliance["symbol"]) == {"RELIANCE"}
    assert list(reliance["side"]) == ["BUY", "SELL"]

    sells = data.bulk_deals(side="sell", from_date=date(2024, 8, 1), to_date=date(2024, 8, 2))
    assert list(sells["symbol"]) == ["TCS", "RELIANCE"]


def test_bulk_deals_snapshot_labelled_off_session(tmp_path: Path) -> None:
    # File downloaded on a Saturday (2026-08-29) carries Friday's deals -- the
    # reader must still surface them for a query on the trade date, 2026-08-28.
    write_staged(
        tmp_path,
        BULK_DEALS,
        date(2026, 8, 29),
        _BULK_HEADER + "28-AUG-2026,RELIANCE,Reliance Industries,ABC FUND,BUY,81000,1300.00,-\n",
    )
    data = NSEData(tmp_path)
    friday = data.bulk_deals(from_date=date(2026, 8, 28), to_date=date(2026, 8, 28))
    assert list(friday["symbol"]) == ["RELIANCE"]
    assert list(friday["trade_date"]) == [date(2026, 8, 28)]
    assert data.bulk_deals(from_date=date(2026, 8, 29), to_date=date(2026, 8, 29)).empty  # no Saturday rows
    # iter_days streams by the file's label date
    from powernse.datasets import BULK_DEALS as _BD

    days = list(data.iter_days(_BD, from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)))
    assert [(d, len(f)) for d, f in days] == [(date(2026, 8, 29), 1)]


def test_block_deals_read(tmp_path: Path) -> None:
    write_staged(
        tmp_path,
        BLOCK_DEALS,
        date(2024, 8, 1),
        _BLOCK_HEADER + "01-AUG-2024,AMAGI,Amagi Media Labs,NOTRE DAME,BUY,142857,560.00\n",
    )
    frame = NSEData(tmp_path).block_deals()
    assert list(frame["symbol"]) == ["AMAGI"]
    assert frame.iloc[0]["quantity"] == 142857


def test_parse_secban_header_and_rows() -> None:
    effective, symbols = parse_secban("Securities in Ban For Trade Date 24-AUG-2026:\n1,SAIL\n2,LICI\n")
    assert effective == date(2026, 8, 24)
    assert symbols == ["SAIL", "LICI"]

    missing_header, only_syms = parse_secban("1,SAIL\n")
    assert missing_header is None
    assert only_syms == ["SAIL"]


def _ban_file(trade_date: str, *symbols: str) -> str:
    rows = "".join(f"{rank},{sym}\n" for rank, sym in enumerate(symbols, start=1))
    return f"Securities in Ban For Trade Date {trade_date}:\n{rows}"


def test_secban_keyed_by_effective_date(tmp_path: Path) -> None:
    write_staged(tmp_path, FO_SECBAN, date(2026, 8, 16), _ban_file("17-AUG-2026", "SAIL", "LICI"))
    write_staged(tmp_path, FO_SECBAN, date(2026, 8, 23), _ban_file("24-AUG-2026", "SAIL"))

    data = NSEData(tmp_path)
    assert data.secban() == {"SAIL"}  # latest effective date
    assert data.secban(date(2026, 8, 17)) == {"SAIL", "LICI"}
    assert data.is_banned("lici", date(2026, 8, 17)) is True
    assert data.is_banned("LICI") is False
    assert data.secban(date(2020, 1, 1)) == set()
