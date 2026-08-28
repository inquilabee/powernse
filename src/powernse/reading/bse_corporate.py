"""Read BSE-sourced dividend amounts that backfill the NSE corporate-actions source."""

import json
from datetime import date

from powernse.datasets import BSE_CORPORATE_ACTIONS
from powernse.parsers.bse import parse_bse_dividend
from powernse.reading.base import ArchiveReader

Row = dict[str, object]


class BseCorporateActionReader(ArchiveReader):
    """Per-share dividend amounts from staged BSE files (each file's date is the ex-date)."""

    def dividend_amounts(self, from_date: date, to_date: date) -> dict[tuple[str, date], float]:
        """``{(symbol, ex_date): total per-share dividend}`` for BSE rows with an ex-date in the window.

        Multiple dividend rows on one ex-date (e.g. final + special) are summed --
        the total cash per share is what a total-return adjustment needs.
        """
        totals: dict[tuple[str, date], float] = {}
        for day in self._archive.staged_dates(BSE_CORPORATE_ACTIONS):
            if not (from_date <= day <= to_date):
                continue
            for row in self._rows(day):
                symbol = str(row.get("short_name") or "").strip().upper()
                amount = parse_bse_dividend(str(row.get("Purpose") or ""))
                if symbol and amount is not None:
                    totals[symbol, day] = totals.get((symbol, day), 0.0) + amount
        return totals

    def _rows(self, day: date) -> list[Row]:
        path = self._archive.staged_path(BSE_CORPORATE_ACTIONS, day)
        if not path.is_file():
            return []
        decoded = json.loads(path.read_text(encoding="utf-8"))
        return [row for row in decoded if isinstance(row, dict)]
