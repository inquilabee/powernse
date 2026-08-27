"""Tests for NSEData OHLC and coverage helpers."""

from datetime import date
from pathlib import Path

import pytest

from powernse import NSEData
from powernse.downloaders.bhavcopy import staged_bhavcopy_csv_path
from powernse.downloaders.corporate_actions import corporate_actions_staged_path


def _write_legacy(tmp_path: Path, trade_date: date, body: str) -> None:
    path = staged_bhavcopy_csv_path(tmp_path, trade_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_ohlc_legacy_and_udiff(tmp_path: Path) -> None:
    _write_legacy(
        tmp_path,
        date(2024, 1, 2),
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
        "RELIANCE,EQ,2500.0,2520.0,2490.0,2510.0,2510.0,2495.0,1000000,2510000000,02-JAN-2024,12000,INE002A01018\n"
        "TCS,EQ,3600.0,3625.0,3590.0,3610.0,3610.0,3595.0,800000,2888000000,02-JAN-2024,9000,INE467B01029\n"
        "RELIANCE,BE,1,1,1,1,1,1,1,1,02-JAN-2024,1,INE002A01018\n",
    )
    _write_legacy(
        tmp_path,
        date(2024, 8, 1),
        "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,LastPric,TtlTradgVol\n"
        "2024-08-01,2024-08-01,CM,NSE,STK,123,INE002A01018,RELIANCE,EQ,2510.0,2530.0,2505.0,2525.0,2525.0,950000\n",
    )

    data = NSEData(tmp_path)
    frame = data.ohlc("reliance", from_date=date(2024, 1, 2), to_date=date(2024, 8, 1))
    assert len(frame) == 2
    assert frame.iloc[0].to_dict() == {
        "trade_date": date(2024, 1, 2),
        "symbol": "RELIANCE",
        "series": "EQ",
        "open": 2500.0,
        "high": 2520.0,
        "low": 2490.0,
        "close": 2510.0,
        "volume": 1_000_000,
        "isin": "INE002A01018",
    }
    assert frame.iloc[1]["close"] == 2525.0
    assert frame.iloc[1]["trade_date"] == date(2024, 8, 1)

    latest = data.latest("RELIANCE")
    assert latest is not None
    assert latest["trade_date"] == date(2024, 8, 1)

    day = data.on(date(2024, 1, 2), symbol="TCS")
    assert len(day) == 1
    assert day.iloc[0]["symbol"] == "TCS"


def test_coverage_gaps(tmp_path: Path) -> None:
    # 2024-01-02 and 2024-01-03 were trading days; only stage the 2nd
    _write_legacy(
        tmp_path,
        date(2024, 1, 2),
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,1,1,1,1,1\n",
    )
    data = NSEData(tmp_path)
    gaps = data.coverage_gaps(from_date=date(2024, 1, 2), to_date=date(2024, 1, 3))
    assert date(2024, 1, 3) in gaps
    assert date(2024, 1, 2) not in gaps


def test_actions_for(tmp_path: Path) -> None:
    path = corporate_actions_staged_path(tmp_path, date(2024, 8, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '[{"symbol":"RELIANCE","subject":"Dividend"},{"symbol":"TCS","subject":"Bonus"}]',
        encoding="utf-8",
    )
    data = NSEData(tmp_path)
    # CA-only archive (no bhavcopy) must still resolve via staged CA dates
    matches = data.actions_for("RELIANCE")
    assert len(matches) == 1
    assert matches[0]["subject"] == "Dividend"


def test_ohlc_skips_bad_numerics(tmp_path: Path) -> None:
    _write_legacy(
        tmp_path,
        date(2024, 1, 2),
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\n"
        "RELIANCE,EQ,bad,2520,2490,2510,100\n"
        "RELIANCE,EQ,2500,2520,2490,2510,100\n",
    )
    frame = NSEData(tmp_path).ohlc("RELIANCE", from_date=date(2024, 1, 2), to_date=date(2024, 1, 2))
    assert len(frame) == 1
    assert frame.iloc[0]["open"] == 2500.0


def test_wide_frame_pivots_one_column_across_symbols(tmp_path: Path) -> None:
    _write_legacy(
        tmp_path,
        date(2024, 1, 2),
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\n"
        "RELIANCE,EQ,2500,2520,2490,2510,100\n"
        "TCS,EQ,3600,3625,3590,3610,80\n",
    )
    _write_legacy(
        tmp_path,
        date(2024, 1, 3),
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\n"
        "RELIANCE,EQ,2510,2530,2505,2525,120\n"
        "TCS,EQ,3610,3630,3600,3620,90\n",
    )

    close = NSEData(tmp_path).wide_frame(column="close", from_date=date(2024, 1, 2), to_date=date(2024, 1, 3))
    assert list(close.columns) == ["RELIANCE", "TCS"]
    assert close.loc[date(2024, 1, 2), "RELIANCE"] == 2510.0
    assert close.loc[date(2024, 1, 3), "TCS"] == 3620.0

    volume = NSEData(tmp_path).wide_frame(
        column="volume", symbols=["TCS"], from_date=date(2024, 1, 2), to_date=date(2024, 1, 3)
    )
    assert list(volume.columns) == ["TCS"]
    assert volume.loc[date(2024, 1, 2), "TCS"] == 80


def test_wide_frame_rejects_unknown_column(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="column must be one of"):
        NSEData(tmp_path).wide_frame(column="not-a-real-column")


def test_ohlc_cli(tmp_path: Path) -> None:
    from powernse.cli import main

    _write_legacy(
        tmp_path,
        date(2024, 1, 2),
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,2500,2520,2490,2510,100\n",
    )
    code = main(["ohlc", "RELIANCE", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path)])
    assert code == 0


def test_ohlc_cli_empty_archive(tmp_path: Path) -> None:
    from powernse.cli import main

    code = main(["ohlc", "RELIANCE", "--root", str(tmp_path)])
    assert code == 1
