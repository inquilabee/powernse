"""Tests for NSEData FO/index queries and CA-adjusted OHLC."""

from datetime import date
from pathlib import Path

from support import staged_path, write_staged

from powernse.data import NSEData
from powernse.datasets import BHAVCOPY, CORPORATE_ACTIONS, FO_BHAVCOPY, INDEX_CLOSES
from powernse.reading.futures import FoFilter

# Bonus/split/dividend subject parsing is covered by tests/test_corporate_actions.py.


def _fo_row(**over: object) -> dict[str, object]:
    base = {
        "symbol": "RELIANCE",
        "instrument_type": "OPTSTK",
        "expiry": date(2024, 8, 29),
        "strike": 770.0,
        "option_type": "CE",
    }
    return {**base, **over}  # type: ignore[return-value]


def test_fofilter_matches_strike_tolerance_and_optional_fields() -> None:
    bar = _fo_row()
    assert FoFilter("RELIANCE").matches(bar)  # bare symbol match
    assert FoFilter("RELIANCE", strike=770.0 + 1e-10).matches(bar)  # within 1e-9
    assert not FoFilter("RELIANCE", strike=770.001).matches(bar)  # outside tolerance
    assert not FoFilter("RELIANCE", strike=100.0).matches(_fo_row(strike=None))  # None strike, wanted set
    assert not FoFilter("TCS").matches(bar)
    assert not FoFilter("RELIANCE", option_type="PE").matches(bar)
    assert FoFilter("RELIANCE", instrument_type="OPTSTK", expiry=date(2024, 8, 29)).matches(bar)


def test_fo_and_index_queries(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 9)
    fo_path = staged_path(tmp_path, FO_BHAVCOPY, trade_date)
    fo_path.parent.mkdir(parents=True, exist_ok=True)
    fo_path.write_text(
        "TradDt,TckrSymb,FinInstrmTp,XpryDt,StrkPric,OptnTp,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,OpnIntrst\n"
        "2024-08-09,RELIANCE,STO,2024-08-29,770.00,CE,0.40,0.50,0.40,0.50,23,1000\n"
        "2024-08-09,RELIANCE,FUTSTK,2024-08-29,,,2500,2510,2490,2505,100,5000\n",
        encoding="utf-8",
    )
    idx_path = staged_path(tmp_path, INDEX_CLOSES, trade_date)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(
        "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value\n"
        "Nifty 50,09-08-2024,24386.85,24419.75,24311.2,24367.5\n",
        encoding="utf-8",
    )

    data = NSEData(tmp_path)
    fo = data.fo_bars("RELIANCE", instrument_type="FUTSTK")
    assert len(fo) == 1
    assert fo.iloc[0]["close"] == 2505.0
    ce = data.fo_bars("RELIANCE", option_type="CE", strike=770.0)
    assert len(ce) == 1
    indexes = data.index("Nifty 50").ohlc()
    assert len(indexes) == 1
    assert indexes.iloc[0]["close"] == 24367.5


def test_ohlc_adjusted_bonus(tmp_path: Path) -> None:
    day_before = date(2024, 8, 1)
    ex_day = date(2024, 8, 2)
    for trade_date, close in ((day_before, 200.0), (ex_day, 100.0)):
        write_staged(
            tmp_path,
            BHAVCOPY,
            trade_date,
            f"SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,{close},{close},{close},{close},100\n",
        )
    ca = staged_path(tmp_path, CORPORATE_ACTIONS, ex_day)
    ca.parent.mkdir(parents=True, exist_ok=True)
    ca.write_text(
        '[{"symbol":"RELIANCE","subject":"Bonus 1:1","exDate":"2024-08-02"}]',
        encoding="utf-8",
    )
    adjusted = NSEData(tmp_path).ohlc_adjusted(
        "RELIANCE",
        from_date=day_before,
        to_date=ex_day,
    )
    assert len(adjusted) == 2
    assert adjusted.iloc[1]["factor"] == 1.0
    assert adjusted.iloc[1]["close"] == 100.0
    assert adjusted.iloc[0]["factor"] == 2.0
    assert adjusted.iloc[0]["close"] == 100.0


def test_ohlc_adjusted_loads_ca_file_before_from_date(tmp_path: Path) -> None:
    """CA JSON labeled before from_date still applies when exDate is in the OHLC window."""
    day_before = date(2024, 8, 1)
    ex_day = date(2024, 8, 2)
    for trade_date, close in ((day_before, 200.0), (ex_day, 100.0)):
        write_staged(
            tmp_path,
            BHAVCOPY,
            trade_date,
            f"SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,{close},{close},{close},{close},100\n",
        )
    ca = staged_path(tmp_path, CORPORATE_ACTIONS, date(2024, 7, 15))
    ca.parent.mkdir(parents=True, exist_ok=True)
    ca.write_text(
        '[{"symbol":"RELIANCE","subject":"Bonus 1:1","exDate":"2024-08-02"}]',
        encoding="utf-8",
    )
    adjusted = NSEData(tmp_path).ohlc_adjusted(
        "RELIANCE",
        from_date=day_before,
        to_date=ex_day,
    )
    assert len(adjusted) == 2
    assert adjusted.iloc[0]["factor"] == 2.0
    assert adjusted.iloc[0]["close"] == 100.0
    assert adjusted.iloc[1]["factor"] == 1.0
    assert adjusted.iloc[1]["close"] == 100.0
