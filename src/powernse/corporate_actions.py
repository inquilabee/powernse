import re
from datetime import date
from enum import StrEnum

import pandas as pd

from powernse.data import NSEData
from powernse.downloaders.corporate_actions import parse_corporate_action_date
from powernse.types import AdjustedOhlcBar, OhlcBar


class CorporateActionType(StrEnum):
    DIVIDEND = "dividend"
    BONUS = "bonus"
    SPLIT = "split"
    RIGHTS = "rights"
    BUYBACK = "buyback"
    MERGER = "merger"
    DEMERGER = "demerger"
    CAPITAL_REDUCTION = "capital_reduction"
    CONSOLIDATION = "consolidation"
    REDEMPTION = "redemption"
    DELISTING = "delisting"
    NAME_CHANGE = "name_change"
    MEETING = "meeting"
    DISTRIBUTION = "distribution"
    OTHER = "other"


# Price-affecting: changes per-share economics and is a real adjustment candidate.
# Non-price-affecting (e.g. MEETING): informational only, never adjusted.
PRICE_AFFECTING_TYPES = frozenset(
    {
        CorporateActionType.DIVIDEND,
        CorporateActionType.BONUS,
        CorporateActionType.SPLIT,
        CorporateActionType.RIGHTS,
        CorporateActionType.BUYBACK,
        CorporateActionType.CAPITAL_REDUCTION,
        CorporateActionType.CONSOLIDATION,
        CorporateActionType.REDEMPTION,
        CorporateActionType.DISTRIBUTION,
    }
)

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
    r"^(?:special\s+)?(?:interim\s+)?div[i]?dend\s*-\s*(?:rs\.?|re\.?)\s*(\d+(?:\.\d+)?)\s*per\s*sh",
    re.IGNORECASE,
)

# Order matters: more specific patterns (scheme/meeting/buyback) must be checked
# before generic ones (bonus/dividend) that would otherwise false-positive on
# subjects like "Scheme Of Arrangement - Bonus - ...".
CLASSIFICATION_PATTERNS: list[tuple[CorporateActionType, re.Pattern[str]]] = [
    (
        CorporateActionType.MEETING,
        re.compile(r"general\s*meeting|board\s*meeting|postal\s*ballot", re.IGNORECASE),
    ),
    (
        CorporateActionType.DEMERGER,
        re.compile(r"demerger|spin[\s-]?off|scheme\s*of\s*arr?angement", re.IGNORECASE),
    ),
    (CorporateActionType.MERGER, re.compile(r"amalgamat|merger|\bmerge\b", re.IGNORECASE)),
    (CorporateActionType.DELISTING, re.compile(r"delist", re.IGNORECASE)),
    (
        CorporateActionType.NAME_CHANGE,
        re.compile(r"name\s*change|change\s*(?:of|in)\s*name", re.IGNORECASE),
    ),
    (CorporateActionType.BUYBACK, re.compile(r"buy[\s-]?back", re.IGNORECASE)),
    (CorporateActionType.RIGHTS, re.compile(r"^rights\b", re.IGNORECASE)),
    (
        CorporateActionType.CAPITAL_REDUCTION,
        re.compile(r"capital\s*reduction|reduction\s*of\s*capital", re.IGNORECASE),
    ),
    (CorporateActionType.CONSOLIDATION, re.compile(r"consolidat", re.IGNORECASE)),
    (CorporateActionType.REDEMPTION, re.compile(r"redempt", re.IGNORECASE)),
    (CorporateActionType.BONUS, re.compile(r"^bonus\b", re.IGNORECASE)),
    (CorporateActionType.SPLIT, re.compile(r"^split|face\s*value\s*split", re.IGNORECASE)),
    (CorporateActionType.DIVIDEND, re.compile(r"div[i]?dend", re.IGNORECASE)),  # incl. "Divdend" typo
    (
        CorporateActionType.DISTRIBUTION,
        re.compile(r"\binterest\b|return\s*(?:on|of)\s*capital|\bspv\b|\bdistribution\b", re.IGNORECASE),
    ),
]


def classify_subject(subject: str) -> CorporateActionType:
    text = subject.strip()
    for action_type, pattern in CLASSIFICATION_PATTERNS:
        if pattern.search(text):
            return action_type
    return CorporateActionType.OTHER


def price_adjustment_factor_from_subject(subject: str) -> float | None:
    """Return a price divisor for a bonus/split CA subject, or None when unrecognized.

    Bonus ``A:B`` (A shares for B held) -> factor ``(A+B)/B``.
    Face-value from->to -> ``old/new``. Split ``N for M`` -> larger/smaller share multiple.
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
    """Return the per-share rupee amount for a plain (or special) dividend CA subject, or None.

    Anchored to the start of the subject and requires the "Per Share"/"Per Sh"
    suffix, so composite records (e.g. REIT/InvIT distributions that mention
    "dividend" as one component among several) don't get misread as a plain
    per-share dividend.
    """
    text = subject.strip()
    if not text:
        return None
    match = DIVIDEND_AMOUNT.match(text)
    if match is None:
        return None
    amount = float(match.group(1))
    return amount if amount > 0 else None


class CorporateActions:
    """A DataFrame view over one symbol's corporate-action history, classified by type,
    and the price adjustments (bonus/split/dividend) derived from it."""

    FRAME_COLUMNS = (
        "symbol",
        "ex_date",
        "type",
        "subject",
        "price_affecting",
        "dividend_amount",
        "price_factor",
    )

    def __init__(self, archive: NSEData | None = None) -> None:
        """``archive`` is only needed for ``frame`` and ``adjusted_ohlc``; ``apply``/``price_events``
        work on bars and records the caller already has."""
        self.archive = archive

    def _require_archive(self) -> NSEData:
        if self.archive is None:
            msg = "CorporateActions needs an archive for this method (construct with CorporateActions(archive))"
            raise ValueError(msg)
        return self.archive

    @staticmethod
    def _classify_record(record: dict[str, object]) -> dict[str, object]:
        subject = str(record.get("subject") or record.get("SUBJECT") or "").strip()
        action_type = classify_subject(subject)
        row: dict[str, object] = {
            "symbol": str(record.get("symbol") or record.get("SYMBOL") or ""),
            "ex_date": parse_corporate_action_date(record),
            "type": action_type,
            "subject": subject,
            "price_affecting": action_type in PRICE_AFFECTING_TYPES,
            "dividend_amount": None,
            "price_factor": None,
        }
        if action_type == CorporateActionType.DIVIDEND:
            row["dividend_amount"] = dividend_amount_from_subject(subject)
        elif action_type in (CorporateActionType.BONUS, CorporateActionType.SPLIT):
            row["price_factor"] = price_adjustment_factor_from_subject(subject)
        return row

    @staticmethod
    def _bonus_split_events(records: list[dict[str, object]]) -> list[tuple[date, float]]:
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
        return events

    @staticmethod
    def _dividend_events(records: list[dict[str, object]]) -> list[tuple[date, float]]:
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
        return events

    @staticmethod
    def _dividend_price_events(
        bars: list[OhlcBar], dividend_events: list[tuple[date, float]]
    ) -> list[tuple[date, float]]:
        """Convert (ex_date, dividend_amount) pairs into divisor events for ``_apply_adjustments``.

        Unlike a split/bonus ratio, a dividend adjustment factor isn't derivable
        from the announcement text alone -- it needs the close on the last trading
        day before the ex-date. The standard total-return convention is
        ``factor = 1 - dividend / prior_close``, stored here as its divisor
        ``prior_close / (prior_close - dividend)``. Events with no prior bar, or a
        dividend at or above the prior close, are skipped rather than producing a
        division error or a negative adjusted price.
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
        return events

    @staticmethod
    def _apply_adjustments(bars: list[OhlcBar], events: list[tuple[date, float]]) -> list[AdjustedOhlcBar]:
        """Apply cumulative CA factors so the newest bar keeps factor 1.0."""
        if not bars:
            return []
        ordered = sorted(bars, key=lambda bar: bar.trade_date)
        events = sorted(events, key=lambda item: item[0])
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
                    volume=round(bar.volume * cumulative),
                    factor=cumulative,
                    isin=bar.isin,
                )
            )
            while event_index >= 0 and events[event_index][0] == bar.trade_date:
                cumulative *= events[event_index][1]
                event_index -= 1
        return list(reversed(result_rev))

    def frame(self, symbol: str, *, from_date: date | None = None, to_date: date | None = None) -> pd.DataFrame:
        archive = self._require_archive()
        records = archive.actions_for(symbol, from_date=from_date, to_date=to_date)
        rows = [self._classify_record(record) for record in records]
        frame = pd.DataFrame(rows, columns=self.FRAME_COLUMNS)
        if frame.empty:
            return frame
        return frame.sort_values("ex_date", kind="stable").reset_index(drop=True)

    def price_events(self, records: list[dict[str, object]], bars: list[OhlcBar]) -> list[tuple[date, float]]:
        """Combined bonus/split/dividend price-adjustment events, ready for ``apply``."""
        dividend_events = self._dividend_events(records)
        return sorted(self._bonus_split_events(records) + self._dividend_price_events(bars, dividend_events))

    def apply(self, bars: list[OhlcBar], records: list[dict[str, object]]) -> list[AdjustedOhlcBar]:
        """Bonus/split/dividend-adjusted bars, cumulative so the newest bar keeps factor 1.0."""
        return self._apply_adjustments(bars, self.price_events(records, bars))

    def adjusted_ohlc(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        series: str = "EQ",
    ) -> list[AdjustedOhlcBar]:
        """Equity OHLC with bonus/split/dividend adjustments from staged CA files."""
        archive = self._require_archive()
        bars = archive.ohlc(symbol, from_date=from_date, to_date=to_date, series=series)
        if not bars:
            return []
        end = to_date or bars[-1].trade_date
        window_start = from_date or bars[0].trade_date
        records = archive.corporate_actions_in_window(symbol, window_start=window_start, end=end)
        return self.apply(bars, records)
