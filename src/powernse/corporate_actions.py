"""Classify raw NSE corporate-action records and derive price adjustments.

Pure: :class:`CorporateActions` is built from the record list (and, for
dividends, the bar frame) the caller already has -- it never reaches back into
an archive. :class:`powernse.data.NSEData` does the wiring.
"""

import re
from datetime import date, datetime
from enum import StrEnum

import numpy as np
import pandas as pd

from powernse.schemas import ADJUSTED_OHLC_SCHEMA, empty_frame

Record = dict[str, object]

CA_DATE_KEYS = ("exDate", "exdate", "recDate", "recordDate", "anouncementDate", "date")
CA_DATE_FORMATS = ("%d-%m-%Y", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y")


def ex_date_of(record: Record) -> date | None:
    """Ex / record / announcement date from a raw CA record (several keys and formats).

    Shared by :class:`~powernse.downloaders.corporate_actions.CorporateActionsDownloader`
    (day bucketing) and :class:`SubjectClassifier` (ex-date classification).
    """
    for key in CA_DATE_KEYS:
        raw = record.get(key)
        if raw is None or not (text := str(raw).strip()):
            continue
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
        for fmt in CA_DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()  # noqa: DTZ007 -- naive date is intended
            except ValueError:
                continue
    return None


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
SPLIT_RATIO = re.compile(r"(?:split|face\s*value\s*split).*?(\d+)\s*(?:for|:|/)\s*(\d+)", re.IGNORECASE)
SPLIT_TO_FROM = re.compile(
    r"face\s*value\s*split.*?from\s*(?:rs\.?|re\.?)?\s*(\d+(?:\.\d+)?).*?to\s*(?:rs\.?|re\.?)?\s*(\d+(?:\.\d+)?)",
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
    (CorporateActionType.MEETING, re.compile(r"general\s*meeting|board\s*meeting|postal\s*ballot", re.IGNORECASE)),
    (CorporateActionType.DEMERGER, re.compile(r"demerger|spin[\s-]?off|scheme\s*of\s*arr?angement", re.IGNORECASE)),
    (CorporateActionType.MERGER, re.compile(r"amalgamat|merger|\bmerge\b", re.IGNORECASE)),
    (CorporateActionType.DELISTING, re.compile(r"delist", re.IGNORECASE)),
    (CorporateActionType.NAME_CHANGE, re.compile(r"name\s*change|change\s*(?:of|in)\s*name", re.IGNORECASE)),
    (CorporateActionType.BUYBACK, re.compile(r"buy[\s-]?back", re.IGNORECASE)),
    (CorporateActionType.RIGHTS, re.compile(r"^rights\b", re.IGNORECASE)),
    (CorporateActionType.CAPITAL_REDUCTION, re.compile(r"capital\s*reduction|reduction\s*of\s*capital", re.IGNORECASE)),
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


def symbol_of(record: Record) -> str:
    """Symbol from a raw CA record (shared with reading.CorporateActionReader)."""
    return str(record.get("symbol") or record.get("SYMBOL") or "")


class SubjectClassifier:
    """Reads a CA record's free-text ``subject`` into a type and the numbers it implies."""

    def __init__(self) -> None:
        self._patterns = CLASSIFICATION_PATTERNS
        self._price_affecting = PRICE_AFFECTING_TYPES

    @staticmethod
    def subject_of(record: Record) -> str:
        return str(record.get("subject") or record.get("SUBJECT") or "").strip()

    def classify(self, subject: str) -> CorporateActionType:
        text = subject.strip()
        for action_type, pattern in self._patterns:
            if pattern.search(text):
                return action_type
        return CorporateActionType.OTHER

    def price_factor(self, subject: str) -> float | None:
        """A price divisor for a bonus/split subject, or ``None`` when unrecognized.

        Bonus ``A:B`` (A shares for B held) -> ``(A+B)/B``. Face-value from->to ->
        ``old/new``. Split ``N for M`` -> larger/smaller share multiple.
        """
        text = subject.strip()
        if not text:
            return None
        if (bonus := BONUS_RATIO.search(text)) is not None:
            shares, held = int(bonus.group(1)), int(bonus.group(2))
            return (shares + held) / held if held > 0 else None
        if (face := SPLIT_TO_FROM.search(text)) is not None:
            old_fv, new_fv = float(face.group(1)), float(face.group(2))
            return old_fv / new_fv if new_fv > 0 else None
        if (split := SPLIT_RATIO.search(text)) is not None:
            left, right = int(split.group(1)), int(split.group(2))
            return max(left, right) / min(left, right) if left > 0 and right > 0 else None
        return None

    def dividend_amount(self, subject: str) -> float | None:
        """Per-share rupee amount for a plain/special dividend subject, or ``None``.

        Anchored to the start and requires the "Per Share"/"Per Sh" suffix, so
        composite records (REIT/InvIT distributions that mention "dividend" as one
        component) aren't misread as a plain per-share dividend.
        """
        match = DIVIDEND_AMOUNT.match(subject.strip())
        if match is None:
            return None
        amount = float(match.group(1))
        return amount if amount > 0 else None

    def describe(self, record: Record) -> Record:
        """One classified row: symbol, ex_date, type, subject, and any derived numbers."""
        subject = self.subject_of(record)
        action_type = self.classify(subject)
        row: Record = {
            "symbol": symbol_of(record),
            "ex_date": ex_date_of(record),
            "type": action_type,
            "subject": subject,
            "price_affecting": action_type in self._price_affecting,
            "dividend_amount": None,
            "price_factor": None,
        }
        if action_type == CorporateActionType.DIVIDEND:
            row["dividend_amount"] = self.dividend_amount(subject)
        elif action_type in (CorporateActionType.BONUS, CorporateActionType.SPLIT):
            row["price_factor"] = self.price_factor(subject)
        return row


SUBJECTS = SubjectClassifier()


class CorporateActions:
    """One symbol's classified CA history and the bonus/split/dividend price math.

    Construct from the records (and, for dividends, the bars) you already have;
    ``NSEData`` fetches those and calls in.
    """

    FRAME_COLUMNS = ("symbol", "ex_date", "type", "subject", "price_affecting", "dividend_amount", "price_factor")

    def __init__(self, records: list[Record], *, classifier: SubjectClassifier = SUBJECTS) -> None:
        self._records = records
        self._classifier = classifier

    def classified(self) -> pd.DataFrame:
        """CA history as a DataFrame, one row per record, sorted by ex-date."""
        rows = [self._classifier.describe(record) for record in self._records]
        frame = pd.DataFrame(rows, columns=list(self.FRAME_COLUMNS))
        if frame.empty:
            return frame
        return frame.sort_values("ex_date", kind="stable").reset_index(drop=True)

    def price_events(self, bars: pd.DataFrame) -> pd.Series:
        """Combined bonus/split/dividend divisor events, ex-date indexed, ready for :meth:`adjust`.

        Duplicate ex-dates stay as separate entries -- the cumulative product in
        ``factors`` multiplies them in correctly either way.
        """
        combined = sorted(self._bonus_split_events() + self._dividend_price_events(bars, self._dividend_events()))
        if not combined:
            return pd.Series(dtype=float)
        dates, factors = zip(*combined, strict=True)
        return pd.Series(factors, index=pd.Index(dates, name="ex_date"), dtype=float)

    def factors(self, bars: pd.DataFrame) -> pd.Series:
        """Per-bar cumulative CA divisor, indexed by ``trade_date`` (sorted).

        ``adjusted_price = raw_price / factor``; the newest bar keeps factor 1.0.
        For bar date ``d`` the divisor is the product of every event multiplier
        with ``d < ex_date <= newest_bar_date``. Events with an ex-date *after*
        the newest bar (announced but not yet effective in the window) are
        dropped before anything is multiplied -- the exact bug class fixed in
        commit 7439f050; keep that filter explicit.
        """
        ordered_dates = bars["trade_date"].sort_values().to_numpy()
        if len(ordered_dates) == 0:
            return pd.Series(dtype=float, name="factor")
        events = self.price_events(bars)
        events = events[events.index <= ordered_dates[-1]].sort_index()
        if events.empty:
            values = np.ones(len(ordered_dates))
        else:
            ex_dates = events.index.to_numpy()
            # suffix_cumprod[k] = product of events[k:]; trailing 1.0 = "no events after".
            suffix_cumprod = np.append(events.to_numpy()[::-1].cumprod()[::-1], 1.0)
            values = suffix_cumprod[np.searchsorted(ex_dates, ordered_dates, side="right")]
        return pd.Series(values, index=pd.Index(ordered_dates, name="trade_date"), name="factor")

    def adjust(self, bars: pd.DataFrame) -> pd.DataFrame:
        """Bonus/split/dividend-adjusted bars, cumulative so the newest bar keeps factor 1.0."""
        if bars.empty:
            return empty_frame(ADJUSTED_OHLC_SCHEMA)
        ordered = bars.sort_values("trade_date").reset_index(drop=True)
        factors = self.factors(ordered).to_numpy()
        adjusted = ordered.assign(
            open=ordered["open"] / factors,
            high=ordered["high"] / factors,
            low=ordered["low"] / factors,
            close=ordered["close"] / factors,
            volume=(ordered["volume"] * factors).round().astype(int),
            factor=factors,
        )[list(ADJUSTED_OHLC_SCHEMA.columns)]
        ADJUSTED_OHLC_SCHEMA.validate(adjusted)
        return adjusted

    def _bonus_split_events(self) -> list[tuple[date, float]]:
        events: list[tuple[date, float]] = []
        for record in self._records:
            factor = self._classifier.price_factor(self._classifier.subject_of(record))
            ex_date = ex_date_of(record)
            if factor is not None and factor != 1.0 and ex_date is not None:
                events.append((ex_date, factor))
        return events

    def _dividend_events(self) -> list[tuple[date, float]]:
        events: list[tuple[date, float]] = []
        for record in self._records:
            amount = self._classifier.dividend_amount(self._classifier.subject_of(record))
            ex_date = ex_date_of(record)
            if amount is not None and ex_date is not None:
                events.append((ex_date, amount))
        return events

    @staticmethod
    def _dividend_price_events(
        bars: pd.DataFrame, dividend_events: list[tuple[date, float]]
    ) -> list[tuple[date, float]]:
        """Turn ``(ex_date, dividend)`` pairs into divisor events.

        Unlike a split/bonus ratio, a dividend factor isn't derivable from the
        text alone -- it needs the close on the last trading day *before* the
        ex-date, found here with a backward as-of join (strictly prior). Total-
        return convention ``factor = 1 - dividend / prior_close``, stored as its
        divisor ``prior_close / (prior_close - dividend)``. Events with no prior
        bar, or a dividend at or above the prior close, are dropped.
        """
        if not dividend_events or bars.empty:
            return []
        events_frame = pd.DataFrame(dividend_events, columns=["ex_date", "amount"]).sort_values("ex_date")
        closes = bars[["trade_date", "close"]].sort_values("trade_date")
        # merge_asof needs sortable numeric/datetime keys, not plain `date` objects (object dtype);
        # join on a throwaway datetime64 view of each column, keep the original date values.
        merged = pd.merge_asof(
            events_frame.assign(_ex_dt=pd.to_datetime(events_frame["ex_date"])),
            closes.assign(_trade_dt=pd.to_datetime(closes["trade_date"])),
            left_on="_ex_dt",
            right_on="_trade_dt",
            direction="backward",
            allow_exact_matches=False,
        )
        results: list[tuple[date, float]] = []
        for ex_date, amount, prior_close in zip(merged["ex_date"], merged["amount"], merged["close"], strict=True):
            if pd.isna(prior_close) or amount <= 0 or prior_close <= amount:
                continue
            results.append((ex_date, prior_close / (prior_close - amount)))
        return results
