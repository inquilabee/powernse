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
    r"face\s*value\s*split.*?from\s*(?:rs\.?\s*)?(\d+(?:\.\d+)?).*?to\s*(?:rs\.?\s*)?(\d+(?:\.\d+)?)",
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
