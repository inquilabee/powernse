"""Read raw corporate-action records out of staged CA JSON files."""

import json
from collections.abc import Iterable
from datetime import date, timedelta

from powernse.constants import CA_ADJUSTMENT_LOOKBACK_DAYS
from powernse.corporate_actions import ex_date_of, symbol_of
from powernse.datasets import CORPORATE_ACTIONS
from powernse.errors import ArchiveError, PayloadError
from powernse.reading.base import ArchiveReader
from powernse.reading.bse_corporate import BseCorporateActionReader
from powernse.window import DateWindow

Record = dict[str, object]


class CorporateActionReader(ArchiveReader):
    """Raw CA records from staged JSON -- no classification or price math (that's
    :class:`powernse.corporate_actions.CorporateActions`)."""

    def raw(self, day: date) -> list[Record]:
        path = self._archive.staged_path(CORPORATE_ACTIONS, day)
        if not path.is_file():
            msg = f"No staged corporate actions for {day.isoformat()} under {self._archive.root}"
            raise ArchiveError(msg)
        decoded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(decoded, list):
            msg = f"Corporate actions payload must be a JSON list for {day.isoformat()}"
            raise PayloadError(msg)
        for item in decoded:
            if not isinstance(item, dict):
                msg = "Corporate actions list items must be objects"
                raise PayloadError(msg)
        return decoded

    def staged_days(self) -> list[date]:
        return self._archive.staged_dates(CORPORATE_ACTIONS)

    def latest_date(self) -> date | None:
        days = self.staged_days()
        return days[-1] if days else None

    def earliest_date(self) -> date | None:
        days = self.staged_days()
        return days[0] if days else None

    def records(
        self,
        symbol: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        bse: BseCorporateActionReader | None = None,
    ) -> list[Record]:
        """CA records mentioning ``symbol`` across the staged window (label-date driven)."""
        # Only walk the CA tree for `latest` when an end is actually missing.
        latest = None if (from_date is not None and to_date is not None) else self.latest_date()
        window = DateWindow.resolve(
            from_date,
            to_date,
            latest=latest,
            missing=f"No staged corporate actions under {self._archive.root}; download data first or pass --from/--to",
        )
        staged = (day for day in window.calendar_days() if self._archive.has_staged(CORPORATE_ACTIONS, day))
        return self._apply_bse_hints(self._collect(symbol, staged), bse)

    def records_in_adjustment_window(
        self, symbol: str, *, window_start: date, end: date, bse: BseCorporateActionReader | None = None
    ) -> list[Record]:
        """CA records whose file date lands in ``[window_start - lookback, end]``.

        Files are picked by their label date, not the record's own ex-date, so an
        ex-date inside the query window is still found when the file is labeled
        earlier -- without walking the whole multi-year CA tree day by day.
        """
        floor = window_start - timedelta(days=CA_ADJUSTMENT_LOOKBACK_DAYS)
        earliest = self.earliest_date()
        if earliest is not None and earliest > floor:
            floor = earliest
        collected = self._collect(symbol, (day for day in self.staged_days() if floor <= day <= end))
        return self._apply_bse_hints(collected, bse)

    def _collect(self, symbol: str, days: Iterable[date]) -> list[Record]:
        needle = symbol.strip().upper()
        return [record for day in days for record in self.raw(day) if symbol_of(record).upper() == needle]

    @staticmethod
    def _apply_bse_hints(records: list[Record], bse: BseCorporateActionReader | None) -> list[Record]:
        """Attach ``dividend_amount_hint`` from BSE where an NSE record's ex-date matches (+/- 1 day)."""
        if bse is None or not records:
            return records
        ex_dates = [day for record in records if (day := ex_date_of(record)) is not None]
        if not ex_dates:
            return records
        amounts = bse.dividend_amounts(min(ex_dates) - timedelta(days=1), max(ex_dates) + timedelta(days=1))
        for record in records:
            hint = CorporateActionReader._bse_hint(record, amounts)
            if hint is not None:
                record["dividend_amount_hint"] = hint
        return records

    @staticmethod
    def _bse_hint(record: Record, amounts: dict[tuple[str, date], float]) -> float | None:
        ex = ex_date_of(record)
        if ex is None:
            return None
        needle = symbol_of(record).upper()
        for delta in (0, -1, 1):
            hit = amounts.get((needle, ex + timedelta(days=delta)))
            if hit is not None:
                return hit
        return None
