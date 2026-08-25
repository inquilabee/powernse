"""Opt-in corporate-action adjustment helpers for equity OHLC."""

import re
from datetime import date

from powernse.downloaders.corporate_actions import parse_corporate_action_date
from powernse.types import AdjustedOhlcBar, OhlcBar

BONUS_RATIO = re.compile(r"bonus\s*(?:issue\s*)?(\d+)\s*:\s*(\d+)", re.IGNORECASE)
SPLIT_RATIO = re.compile(
    r"(?:split|face\s*value\s*split).*?(\d+)\s*(?:for|:|/)\s*(\d+)",
    re.IGNORECASE,
)
SPLIT_TO_FROM = re.compile(
    r"face\s*value\s*split.*?from\s*(?:rs\.?|re\.?)?\s*(\d+(?:\.\d+)?)"
    r".*?to\s*(?:rs\.?|re\.?)?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
DIVIDEND_AMOUNT = re.compile(
    r"^(?:interim\s+)?dividend\s*-\s*(?:rs\.?|re\.?)\s*(\d+(?:\.\d+)?)\s*per\s*sh",
    re.IGNORECASE,
)


def price_adjustment_factor_from_subject(subject: str) -> float | None:
    """Return a price divisor for a CA subject, or None when unrecognized.

    Bonus ``A:B`` (A shares for B held) → factor ``(A+B)/B``.
    Face-value from→to → ``old/new``. Split ``N for M`` → larger/smaller share multiple.
    """
    text = subject.strip()
    if not text:
        return None
    bonus = BONUS_RATIO.search(text)
    if bonus is not None:
        bonus_shares = int(bonus.group(1))
        held = int(bonus.group(2))
        if held <= 0:
            return None
        return (bonus_shares + held) / held
    face = SPLIT_TO_FROM.search(text)
    if face is not None:
        old_fv = float(face.group(1))
        new_fv = float(face.group(2))
        if new_fv <= 0:
            return None
        return old_fv / new_fv
    split = SPLIT_RATIO.search(text)
    if split is not None:
        left = int(split.group(1))
        right = int(split.group(2))
        if left <= 0 or right <= 0:
            return None
        return max(left, right) / min(left, right)
    return None


def dividend_amount_from_subject(subject: str) -> float | None:
    """Return the per-share rupee amount for a plain dividend CA subject, or None.

    Deliberately anchored to the start of the subject and requires the
    "Per Share"/"Per Sh" suffix, so composite records (e.g. REIT/InvIT
    distributions that mention "dividend" as one component among several)
    don't get misread as a plain per-share dividend.
    """
    text = subject.strip()
    if not text:
        return None
    match = DIVIDEND_AMOUNT.match(text)
    if match is None:
        return None
    amount = float(match.group(1))
    return amount if amount > 0 else None


def corporate_action_price_events(records: list[dict[str, object]]) -> list[tuple[date, float]]:
    """Extract ``(ex_date, price_divisor)`` pairs from corporate-action records."""
    events: list[tuple[date, float]] = []
    for record in records:
        subject = str(record.get("subject") or record.get("SUBJECT") or "")
        factor = price_adjustment_factor_from_subject(subject)
        if factor is None or factor == 1.0:
            continue
        ex_date = parse_corporate_action_date(record)
        if ex_date is None:
            continue
        events.append((ex_date, factor))
    events.sort(key=lambda item: item[0])
    return events


def corporate_action_dividend_events(records: list[dict[str, object]]) -> list[tuple[date, float]]:
    """Extract ``(ex_date, dividend_amount)`` pairs from corporate-action records."""
    events: list[tuple[date, float]] = []
    for record in records:
        subject = str(record.get("subject") or record.get("SUBJECT") or "")
        amount = dividend_amount_from_subject(subject)
        if amount is None:
            continue
        ex_date = parse_corporate_action_date(record)
        if ex_date is None:
            continue
        events.append((ex_date, amount))
    events.sort(key=lambda item: item[0])
    return events


def dividend_price_events(bars: list[OhlcBar], dividend_events: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """Convert ``(ex_date, dividend_amount)`` pairs into ``apply_price_adjustments`` divisor events.

    Unlike a split/bonus ratio, a dividend adjustment factor isn't derivable
    from the announcement text alone -- it needs the close on the last
    trading day before the ex-date. The standard total-return convention is
    ``factor = 1 - dividend / prior_close``; stored here as its divisor
    ``prior_close / (prior_close - dividend)`` so the result plugs directly
    into ``apply_price_adjustments``, which always divides older bars by the
    cumulative event factor. Events with no prior bar, or a dividend at or
    above the prior close, are skipped rather than producing a division
    error or a negative adjusted price.
    """
    by_date = {bar.trade_date: bar for bar in bars}
    ordered_dates = sorted(by_date)
    events: list[tuple[date, float]] = []
    for ex_date, amount in dividend_events:
        prior_dates = [d for d in ordered_dates if d < ex_date]
        if not prior_dates:
            continue
        prior_close = by_date[prior_dates[-1]].close
        if amount <= 0 or prior_close <= amount:
            continue
        events.append((ex_date, prior_close / (prior_close - amount)))
    events.sort(key=lambda item: item[0])
    return events


def apply_price_adjustments(bars: list[OhlcBar], events: list[tuple[date, float]]) -> list[AdjustedOhlcBar]:
    """Apply cumulative CA factors so the newest bar keeps factor 1.0."""
    if not bars:
        return []
    ordered = sorted(bars, key=lambda bar: bar.trade_date)
    cumulative = 1.0
    event_index = len(events) - 1
    result_rev: list[AdjustedOhlcBar] = []
    for i, bar in enumerate(reversed(ordered)):
        newer = ordered[len(ordered) - i] if i > 0 else None
        upper = newer.trade_date if newer is not None else date.max
        while event_index >= 0 and bar.trade_date < events[event_index][0] <= upper:
            cumulative *= events[event_index][1]
            event_index -= 1
        result_rev.append(
            AdjustedOhlcBar(
                trade_date=bar.trade_date,
                symbol=bar.symbol,
                series=bar.series,
                open=bar.open / cumulative,
                high=bar.high / cumulative,
                low=bar.low / cumulative,
                close=bar.close / cumulative,
                volume=int(round(bar.volume * cumulative)),
                factor=cumulative,
                isin=bar.isin,
            )
        )
        while event_index >= 0 and events[event_index][0] == bar.trade_date:
            cumulative *= events[event_index][1]
            event_index -= 1
    return list(reversed(result_rev))
