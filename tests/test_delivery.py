"""Typed delivery / traded-value reads from staged sec_bhavdata_full."""

from datetime import date
from pathlib import Path

from support import write_staged

from powernse import NSEData
from powernse.datasets import FULL_BHAVCOPY

_HEADER = (
    "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, "
    "CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
)


def _full(*rows: str) -> str:
    return _HEADER + "".join(r + "\n" for r in rows)


def test_delivery_reads_pct_qty_and_turnover(tmp_path: Path) -> None:
    write_staged(
        tmp_path,
        FULL_BHAVCOPY,
        date(2024, 8, 1),
        _full(
            "RELIANCE, EQ, 01-Aug-2024, 100, 100, 105, 99, 104, 104, 102, 200000, 400.5, 3000, 120000, 60.00",
            "ILLIQ, GS, 01-Aug-2024, 50, 50, 50, 50, 50, 50, 50, 10, 0.01, 1, -, -",
        ),
    )
    write_staged(
        tmp_path,
        FULL_BHAVCOPY,
        date(2024, 8, 2),
        _full("RELIANCE, EQ, 02-Aug-2024, 104, 104, 108, 103, 107, 107, 105, 250000, 525.0, 4000, 175000, 70.00"),
    )

    data = NSEData(tmp_path)
    frame = data.delivery("reliance", from_date=date(2024, 8, 1), to_date=date(2024, 8, 2))
    assert list(frame["trade_date"]) == [date(2024, 8, 1), date(2024, 8, 2)]
    assert list(frame["delivery_pct"]) == [60.0, 70.0]
    assert list(frame["delivery_qty"]) == [120000, 175000]
    assert frame.iloc[0]["turnover_lacs"] == 400.5
    assert frame.iloc[0]["trades"] == 3000

    # the "-" GS row parses with null delivery fields
    day = data.delivery_on(date(2024, 8, 1), series=None)
    illiq = day[day["symbol"] == "ILLIQ"].iloc[0]
    assert bool(illiq[["delivery_qty", "delivery_pct"]].isna().all())


def test_delivery_frame_pivots(tmp_path: Path) -> None:
    for day, reliance_pct, tcs_pct in ((date(2024, 8, 1), "60.00", "55.00"), (date(2024, 8, 2), "62.00", "58.00")):
        write_staged(
            tmp_path,
            FULL_BHAVCOPY,
            day,
            _full(
                f"RELIANCE, EQ, {day.strftime('%d-%b-%Y')}, 1, 1, 1, 1, 1, 1, 1, 100, 1.0, 10, 60, {reliance_pct}",
                f"TCS, EQ, {day.strftime('%d-%b-%Y')}, 1, 1, 1, 1, 1, 1, 1, 100, 1.0, 10, 55, {tcs_pct}",
            ),
        )
    pct = NSEData(tmp_path).delivery_frame(from_date=date(2024, 8, 1), to_date=date(2024, 8, 2))
    assert list(pct.columns) == ["RELIANCE", "TCS"]
    assert pct.loc[date(2024, 8, 2), "RELIANCE"] == 62.0
    qty = NSEData(tmp_path).delivery_frame(column="delivery_qty", symbols=["TCS"])
    assert list(qty.columns) == ["TCS"]
