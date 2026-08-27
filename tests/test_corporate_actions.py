import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from powernse.corporate_actions import (
    CorporateActions,
    CorporateActionType,
    classify_subject,
    dividend_amount_from_subject,
    price_adjustment_factor_from_subject,
)
from powernse.data import NSEData
from powernse.downloaders.corporate_actions import corporate_actions_staged_path
from powernse.schemas import OHLC_SCHEMA


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Bonus 1:1", 2.0),
        ("Face Value Split from Rs 10 to Rs 5", 2.0),
        ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share", 10.0),
        ("Dividend", None),
    ],
)
def test_price_adjustment_factor_from_subject(subject: str, expected: float | None) -> None:
    assert price_adjustment_factor_from_subject(subject) == expected


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Dividend - Rs 270 Per Share", 270.0),
        ("Dividend - Re 0.25 Per Sh", 0.25),
        ("Interim Dividend - Rs 4.50 Per Share", 4.50),
        ("Special Dividend - Rs 25 Per Share", 25.0),
        ("Special Interim Dividend - Rs 7.50 Per Share", 7.50),
        ("Bonus 1:1", None),
        (
            "Distribution - Rs 6.31 Per Unit Consisting Of Re 0.37 Per Unit As Interest/"
            " Re 0.80 Per Unit As Dividend/ Rs 5.14 Per Unit As Repayment Of Spv Level Debt",
            None,
        ),
        ("", None),
    ],
)
def test_dividend_amount_from_subject(subject: str, expected: float | None) -> None:
    assert dividend_amount_from_subject(subject) == expected


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Dividend - Rs 2.50 Per Share", CorporateActionType.DIVIDEND),
        ("Special Dividend - Rs 30 Per Share", CorporateActionType.DIVIDEND),
        ("Interim Divdend - Rs 2 Per Share", CorporateActionType.DIVIDEND),  # real NSE typo
        ("Bonus 1:1", CorporateActionType.BONUS),
        ("Face Value Split from Rs 10 to Rs 5", CorporateActionType.SPLIT),
        ("Rights 1:5", CorporateActionType.RIGHTS),
        ("Buy Back Of Shares", CorporateActionType.BUYBACK),
        ("Amalgamation", CorporateActionType.MERGER),
        ("Scheme Of Arangement- Bonus - 1 Debenture For 1 Equity Share Held", CorporateActionType.DEMERGER),
        ("Annual General Meeting", CorporateActionType.MEETING),
        (
            "Interest Amount - Rs 2.66 Per Unit / Return On Capital - Rs 0.52 Per Unit",
            CorporateActionType.DISTRIBUTION,
        ),
        ("Something Entirely Unrecognized", CorporateActionType.OTHER),
    ],
)
def test_classify_subject(subject: str, expected: CorporateActionType) -> None:
    assert classify_subject(subject) == expected


def test_frame_classifies_and_sorts(tmp_path: Path) -> None:
    for trade_date, records in [
        (date(2024, 8, 1), [{"symbol": "RELIANCE", "subject": "Bonus 1:1", "exDate": "2024-08-01"}]),
        (
            date(2024, 1, 1),
            [{"symbol": "RELIANCE", "subject": "Dividend - Rs 5 Per Share", "exDate": "2024-01-01"}],
        ),
    ]:
        path = corporate_actions_staged_path(tmp_path, trade_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records), encoding="utf-8")

    frame = CorporateActions(NSEData(tmp_path)).frame(
        "RELIANCE", from_date=date(2024, 1, 1), to_date=date(2024, 8, 1)
    )
    assert list(frame["type"]) == [CorporateActionType.DIVIDEND, CorporateActionType.BONUS]
    assert list(frame["ex_date"]) == [date(2024, 1, 1), date(2024, 8, 1)]
    assert frame.loc[0, "dividend_amount"] == 5.0
    assert frame.loc[1, "price_factor"] == 2.0
    assert list(frame["price_affecting"]) == [True, True]


def _bars_frame(*rows: tuple[date, float]) -> pd.DataFrame:
    """An OhlcSchema-shaped frame for symbol "TEST" from (trade_date, close) pairs (open=high=low=close)."""
    return pd.DataFrame(
        [
            {
                "trade_date": trade_date,
                "symbol": "TEST",
                "series": "EQ",
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1000,
                "isin": None,
            }
            for trade_date, close in rows
        ],
        columns=list(OHLC_SCHEMA.columns),
    )


def test_dividend_adjustment_reduces_only_prior_bars() -> None:
    bars = _bars_frame((date(2024, 1, 1), 100.0), (date(2024, 1, 2), 95.0))
    records = [{"subject": "Dividend - Rs 5 Per Share", "exDate": "2024-01-02"}]
    corp_actions = CorporateActions(archive=None)  # .apply()/.price_events() never touch self.archive

    price_events = corp_actions.price_events(records, bars)
    assert price_events.to_dict() == {date(2024, 1, 2): 100.0 / (100.0 - 5.0)}

    adjusted = corp_actions.apply(bars, records)
    assert adjusted.iloc[0]["close"] == pytest.approx(95.0)  # pre-ex-date bar, adjusted down
    assert adjusted.iloc[1]["close"] == pytest.approx(95.0)  # ex-date bar itself, untouched


def test_apply_ignores_events_not_yet_effective() -> None:
    """A CA announced (and staged) ahead of its ex-date must not adjust bars before it happens.

    ``corporate_actions_in_window`` can legitimately hand back a record whose real
    ex-date is beyond the newest loaded bar (the announcement file is selected by
    file-day, not ex-date). Regression for a bug where such an event's factor was
    applied to every bar in the window because the newest bar's upper bound was
    unbounded (``date.max``). Re-verified explicitly here (not just "still passes")
    after the vectorized rewrite of ``_apply_adjustments`` in commit 7439f050's wake.
    """
    bars = _bars_frame((date(2024, 8, 1), 200.0), (date(2024, 8, 2), 202.0))
    records = [{"subject": "Bonus 1:1", "exDate": "2024-09-15"}]  # ex-date after both bars
    corp_actions = CorporateActions(archive=None)

    # price_events() derives the raw (ex_date, factor) pair regardless of the bar window;
    # apply()/_apply_adjustments() is what must drop events beyond the newest bar.
    assert corp_actions.price_events(records, bars).to_dict() == {date(2024, 9, 15): 2.0}
    adjusted = corp_actions.apply(bars, records)
    assert adjusted["factor"].tolist() == [1.0, 1.0]
    assert adjusted["close"].tolist() == [200.0, 202.0]
