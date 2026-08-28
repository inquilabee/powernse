"""Parse the staged ``fo_secban.csv`` snapshot.

The file is a one-line header naming the effective trade date, then ``rank,SYMBOL``
rows::

    Securities in Ban For Trade Date 24-AUG-2026:
    1,BANDHANBNK
    2,LICI
"""

import contextlib
import re
from datetime import date, datetime

TRADE_DATE_RE = re.compile(r"Trade Date\s+(\d{2}-[A-Za-z]{3}-\d{4})", re.IGNORECASE)
BAN_ROW_RE = re.compile(r"^\d+\s*,\s*(\S.*)$")


def parse_secban(text: str) -> tuple[date | None, list[str]]:
    """``(effective trade date, banned symbols)`` from the ``fo_secban`` file's text.

    The date is ``None`` when the header line is missing or unparseable; the
    symbol list preserves file order and is de-duplicated.
    """
    effective: date | None = None
    symbols: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if effective is None and (match := TRADE_DATE_RE.search(line)):
            with contextlib.suppress(ValueError):
                effective = datetime.strptime(match.group(1), "%d-%b-%Y").date()  # noqa: DTZ007 -- naive date
        elif (row := BAN_ROW_RE.match(line)) and (symbol := row.group(1).strip().upper()) not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    return effective, symbols
