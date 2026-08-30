import json
from datetime import date
from pathlib import Path

import pytest
from support import bars_frame, staged_path, write_staged

from powernse.corporate_actions import SUBJECTS, CorporateActions, CorporateActionType, dividend_hint_of
from powernse.data import NSEData
from powernse.datasets import BHAVCOPY, BSE_CORPORATE_ACTIONS, CORPORATE_ACTIONS


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Bonus 1:1", 2.0),
        ("Face Value Split from Rs 10 to Rs 5", 2.0),
        ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share", 10.0),
        ("Dividend", None),
    ],
)
def test_price_factor(subject: str, expected: float | None) -> None:
    assert SUBJECTS.price_factor(subject) == expected


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
def test_dividend_amount(subject: str, expected: float | None) -> None:
    assert SUBJECTS.dividend_amount(subject) == expected


@pytest.mark.parametrize(
    ("subject", "face_value", "expected"),
    [
        ("Div 30%", 10.0, 3.0),
        ("Div - 18%", 10.0, 1.8),
        ("Agm/Div-50%/Rights-1:6", 2.0, 1.0),
        ("Dividend 15 %", 100.0, 15.0),
        ("Div 30%", None, None),  # needs face value
        ("Dividend - Rs 5 Per Share", 10.0, 5.0),  # explicit rupees still win
    ],
)
def test_percent_dividend(subject: str, face_value: float | None, expected: float | None) -> None:
    assert SUBJECTS.dividend_amount(subject, face_value=face_value) == expected


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Consolidation Of Equity Shares From Re 1 Per Share To Rs 10 Per Share", 0.1),
        ("Consolidation Rs 2 To Rs 10", 0.2),
        ("Consolidation Of Equity Shares", None),
        ("Face Value Split from Rs 10 to Rs 5", None),  # not a consolidation subject
    ],
)
def test_consolidation_factor(subject: str, expected: float | None) -> None:
    assert SUBJECTS.consolidation_factor(subject) == expected


def test_percent_dividend_and_consolidation_adjust_bars() -> None:
    bars = bars_frame((date(2024, 1, 1), 100.0), (date(2024, 1, 2), 100.0), (date(2024, 1, 3), 100.0))
    records = [
        {"symbol": "TEST", "subject": "Div 20%", "faceVal": "10", "exDate": "2024-01-02"},  # Rs 2/sh
        {"symbol": "TEST", "subject": "Consolidation From Re 1 To Rs 2", "faceVal": "2", "exDate": "2024-01-03"},
    ]
    adjusted = CorporateActions(records).adjust(bars).set_index("trade_date")["close"]
    assert adjusted[date(2024, 1, 3)] == 100.0  # newest bar untouched
    assert adjusted[date(2024, 1, 2)] == 200.0  # consolidation divisor 0.5 only: 100 / 0.5
    # 2024-01-01: dividend (100/98) x consolidation (0.5) -> 100 / (98/100 * 0.5 ... ) = 196.0
    assert adjusted[date(2024, 1, 1)] == pytest.approx(196.0)


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
def test_classify(subject: str, expected: CorporateActionType) -> None:
    assert SUBJECTS.classify(subject) == expected


def test_frame_classifies_and_sorts(tmp_path: Path) -> None:
    for trade_date, records in [
        (date(2024, 8, 1), [{"symbol": "RELIANCE", "subject": "Bonus 1:1", "exDate": "2024-08-01"}]),
        (date(2024, 1, 1), [{"symbol": "RELIANCE", "subject": "Dividend - Rs 5 Per Share", "exDate": "2024-01-01"}]),
    ]:
        path = staged_path(tmp_path, CORPORATE_ACTIONS, trade_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records), encoding="utf-8")

    frame = NSEData(tmp_path).corporate_actions("RELIANCE", from_date=date(2024, 1, 1), to_date=date(2024, 8, 1))
    assert list(frame["type"]) == [CorporateActionType.DIVIDEND, CorporateActionType.BONUS]
    assert list(frame["ex_date"]) == [date(2024, 1, 1), date(2024, 8, 1)]
    assert frame.loc[0, "dividend_amount"] == 5.0
    assert frame.loc[1, "price_factor"] == 2.0
    assert list(frame["price_affecting"]) == [True, True]


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Rights 1:1 @ Premium Rs 90/-", (1, 1, 100.0)),
        ("Rights 2:5 @ Premium Rs.50/- Per Share", (2, 5, 60.0)),
        ("Rights 1:2 Prem@Rs.79/-", (1, 2, 89.0)),
        ("Rights 4:7 At Par", (4, 7, 10.0)),
        ("Interim Dividend- Rs 3 Per Share / Rights 1:16 @ Premium Rs 554 Per Share", (1, 16, 564.0)),
        ("Rights 1:1", None),  # no premium / par
        ("Rights - 7 Ccps And 7 Warrants:40", None),  # non-equity
        ("Rights Equity/Warrant", None),
    ],
)
def test_rights_terms(subject: str, expected: tuple[int, int, float] | None) -> None:
    terms = SUBJECTS.rights_terms(subject, face_value=10.0)
    got = None if terms is None else (terms.new, terms.held, terms.subscription_price)
    assert got == expected


def test_rights_terms_needs_face_value() -> None:
    assert SUBJECTS.rights_terms("Rights 1:1 @ Premium Rs 90/-", face_value=None) is None


def test_rights_adjustment_is_opt_in_and_uses_terp() -> None:
    # prior close (2024-01-01) = 200; Rights 1:1 @ Premium Rs 90 on faceVal 10 -> S = 100
    # TERP = (1*200 + 1*100) / 2 = 150 ; divisor = 200 / 150
    bars = bars_frame((date(2024, 1, 1), 200.0), (date(2024, 1, 2), 150.0))
    records = [{"symbol": "TEST", "subject": "Rights 1:1 @ Premium Rs 90", "faceVal": "10", "exDate": "2024-01-02"}]

    assert CorporateActions(records).price_events(bars).empty  # default: rights not applied

    withr = CorporateActions(records, apply={"bonus", "split", "consolidation", "dividend", "rights"})
    assert withr.price_events(bars).to_dict() == {date(2024, 1, 2): pytest.approx(200.0 / 150.0)}
    adjusted = withr.adjust(bars).set_index("trade_date")["close"]
    assert adjusted[date(2024, 1, 1)] == pytest.approx(150.0)  # 200 / (200/150)
    assert adjusted[date(2024, 1, 2)] == 150.0  # newest bar untouched


def test_skipped_events_reports_unparsed_rights() -> None:
    records = [
        {"symbol": "A", "subject": "Rights 1:1 @ Premium Rs 5", "faceVal": "10", "exDate": "2024-02-01"},
        {"symbol": "B", "subject": "Rights Equity/Warrant", "faceVal": "10", "exDate": "2024-03-01"},
    ]
    skipped = CorporateActions(records, apply={"rights"}).skipped_events()
    assert [(s.symbol, s.type) for s in skipped] == [("B", CorporateActionType.RIGHTS)]


def test_rights_deep_otm_dropped() -> None:
    # subscription price far above market -> TERP >= prior close -> no adjustment
    bars = bars_frame((date(2024, 1, 1), 50.0), (date(2024, 1, 2), 50.0))
    records = [{"symbol": "T", "subject": "Rights 1:1 @ Premium Rs 990", "faceVal": "10", "exDate": "2024-01-02"}]
    assert CorporateActions(records, apply={"rights"}).price_events(bars).empty


def test_apply_rejects_unknown_category() -> None:
    with pytest.raises(ValueError, match="apply must be a subset"):
        CorporateActions([], apply={"bonus", "wat"})


def test_dividend_adjustment_reduces_only_prior_bars() -> None:
    bars = bars_frame((date(2024, 1, 1), 100.0), (date(2024, 1, 2), 95.0))
    actions = CorporateActions([{"subject": "Dividend - Rs 5 Per Share", "exDate": "2024-01-02"}])

    assert actions.price_events(bars).to_dict() == {date(2024, 1, 2): 100.0 / (100.0 - 5.0)}

    adjusted = actions.adjust(bars)
    assert adjusted.iloc[0]["close"] == pytest.approx(95.0)  # pre-ex-date bar, adjusted down
    assert adjusted.iloc[1]["close"] == pytest.approx(95.0)  # ex-date bar itself, untouched


def test_apply_ignores_events_not_yet_effective() -> None:
    """A CA announced (and staged) ahead of its ex-date must not adjust bars before it happens.

    ``records_in_adjustment_window`` can legitimately hand back a record whose real
    ex-date is beyond the newest loaded bar (the file is selected by label date,
    not ex-date). Regression for a bug where such an event's factor was applied to
    every bar because the newest bar's upper bound was unbounded (``date.max``).
    Re-verified explicitly after the vectorized `factors()` extraction.
    """
    bars = bars_frame((date(2024, 8, 1), 200.0), (date(2024, 8, 2), 202.0))
    actions = CorporateActions([{"subject": "Bonus 1:1", "exDate": "2024-09-15"}])  # ex-date after both bars

    # price_events() derives the raw (ex_date, factor) pair regardless of the bar window;
    # adjust()/factors() is what must drop events beyond the newest bar.
    assert actions.price_events(bars).to_dict() == {date(2024, 9, 15): 2.0}
    adjusted = actions.adjust(bars)
    assert adjusted["factor"].tolist() == [1.0, 1.0]
    assert adjusted["close"].tolist() == [200.0, 202.0]


def _stage_bse(root: Path, day: date, rows: list[dict[str, object]]) -> None:
    path = staged_path(root, BSE_CORPORATE_ACTIONS, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_bse_backfills_dividend_amount_missing_from_nse_subject(tmp_path: Path) -> None:
    day_before, ex_day = date(2024, 8, 1), date(2024, 8, 2)
    for trade_date, close in ((day_before, 100.0), (ex_day, 98.0)):
        write_staged(
            tmp_path,
            BHAVCOPY,
            trade_date,
            f"SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,{close},{close},{close},{close},100\n",
        )
    ca = staged_path(tmp_path, CORPORATE_ACTIONS, ex_day)
    ca.parent.mkdir(parents=True, exist_ok=True)
    # NSE subject: dividend, but no per-share figure in the text
    ca.write_text('[{"symbol":"RELIANCE","subject":"Dividend","exDate":"2024-08-02","faceVal":"10"}]', encoding="utf-8")
    # BSE has the amount, one calendar day early (ex-date tolerance +/- 1)
    _stage_bse(tmp_path, date(2024, 8, 1), [{"short_name": "RELIANCE", "Purpose": "Final Dividend - Rs. - 2.0000"}])

    data = NSEData(tmp_path)
    assert data.corporate_actions("RELIANCE", from_date=day_before, to_date=ex_day).loc[0, "dividend_amount"] == 2.0

    adjusted = data.ohlc_adjusted("RELIANCE", from_date=day_before, to_date=ex_day).set_index("trade_date")["close"]
    # prior close 100, dividend 2 -> divisor 100/98 on the pre-ex-date bar
    assert adjusted[day_before] == pytest.approx(98.0)
    assert adjusted[ex_day] == 98.0


def test_nse_subject_amount_wins_over_bse() -> None:
    record = {
        "symbol": "X",
        "subject": "Dividend - Rs 5 Per Share",
        "exDate": "2024-08-02",
        "dividend_amount_hint": 9.0,
    }
    events = CorporateActions([record]).price_events(bars_frame((date(2024, 8, 1), 100.0), (date(2024, 8, 2), 95.0)))
    assert events.to_dict() == {date(2024, 8, 2): 100.0 / (100.0 - 5.0)}  # 5 from the subject, not 9 from BSE


def test_dividend_hint_of_guards() -> None:
    assert dividend_hint_of({"dividend_amount_hint": 3.5}) == 3.5
    assert dividend_hint_of({"dividend_amount_hint": 0}) is None
    assert dividend_hint_of({"dividend_amount_hint": True}) is None
    assert dividend_hint_of({}) is None


def _write_bhav_series(root: Path, closes: dict[date, float]) -> None:
    for day, close in closes.items():
        write_staged(
            root,
            BHAVCOPY,
            day,
            f"SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nETF,EQ,{close},{close},{close},{close},1000\n",
        )


def test_price_anomalies_flags_unexplained_split(tmp_path: Path) -> None:
    _write_bhav_series(
        tmp_path,
        {date(2019, 12, 17): 1290.0, date(2019, 12, 18): 1292.0, date(2019, 12, 19): 129.0, date(2019, 12, 20): 130.0},
    )
    hits = NSEData(tmp_path).price_anomalies("ETF", from_date=date(2019, 12, 1), to_date=date(2019, 12, 31))
    assert len(hits) == 1
    a = hits[0]
    assert a.trade_date == date(2019, 12, 19)
    assert a.ca_type is None  # nothing in the CA archive explains a -90% day
    assert a.pct_change == pytest.approx(-0.9, abs=0.01)


def test_price_anomalies_explained_by_staged_ca(tmp_path: Path) -> None:
    _write_bhav_series(tmp_path, {date(2024, 8, 1): 200.0, date(2024, 8, 2): 100.0, date(2024, 8, 5): 101.0})
    ca = staged_path(tmp_path, CORPORATE_ACTIONS, date(2024, 8, 2))
    ca.parent.mkdir(parents=True, exist_ok=True)
    ca.write_text('[{"symbol":"ETF","subject":"Bonus 1:1","exDate":"2024-08-02"}]', encoding="utf-8")
    hits = NSEData(tmp_path).price_anomalies("ETF", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
    assert [(h.trade_date, h.ca_type) for h in hits] == [(date(2024, 8, 2), "bonus")]
