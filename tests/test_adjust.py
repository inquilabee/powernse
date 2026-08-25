from datetime import date

import pytest

from powernse.adjust import (
    apply_price_adjustments,
    corporate_action_dividend_events,
    dividend_amount_from_subject,
    dividend_price_events,
    price_adjustment_factor_from_subject,
)
from powernse.types import OhlcBar


def test_split_to_from_accepts_re_for_one_rupee_face_value() -> None:
    subject = "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share"
    assert price_adjustment_factor_from_subject(subject) == 10.0


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Dividend - Rs 270 Per Share", 270.0),
        ("Dividend - Re 0.25 Per Sh", 0.25),
        ("Interim Dividend - Rs 4.50 Per Share", 4.50),
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


def test_corporate_action_dividend_events_skips_non_dividend_records() -> None:
    records = [
        {"subject": "Dividend - Rs 5 Per Share", "exDate": "2024-08-01"},
        {"subject": "Bonus 1:1", "exDate": "2024-09-01"},
    ]
    assert corporate_action_dividend_events(records) == [(date(2024, 8, 1), 5.0)]


def _bar(trade_date: date, close: float) -> OhlcBar:
    return OhlcBar(
        trade_date=trade_date,
        symbol="TEST",
        series="EQ",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )


def test_dividend_adjustment_reduces_only_prior_bars() -> None:
    bars = [_bar(date(2024, 1, 1), 100.0), _bar(date(2024, 1, 2), 95.0)]
    dividend_events = [(date(2024, 1, 2), 5.0)]

    price_events = dividend_price_events(bars, dividend_events)
    assert price_events == [(date(2024, 1, 2), 100.0 / (100.0 - 5.0))]

    adjusted = apply_price_adjustments(bars, price_events)
    assert adjusted[0].close == pytest.approx(95.0)  # pre-ex-date bar, adjusted down
    assert adjusted[1].close == pytest.approx(95.0)  # ex-date bar itself, untouched
