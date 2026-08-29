"""Parse rows from BSE's ``DefaultData/w`` corporate-actions feed.

Only the per-share **dividend amount** is extracted -- it sits in the free-text
``Purpose`` field as ``"<kind> Dividend - Rs. - <amount>"``. Everything else in
the BSE feed (rights, bonus, interest, redemptions) is covered better, or not at
all, by the NSE source.
"""

import re

BSE_DIVIDEND_AMOUNT = re.compile(r"dividend\s*-\s*rs\.?\s*-\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_bse_dividend(purpose: str) -> float | None:
    """Per-share rupee dividend from a BSE ``Purpose`` string, or ``None``."""
    match = BSE_DIVIDEND_AMOUNT.search(purpose)
    if match is None:
        return None
    amount = float(match.group(1))
    return amount if amount > 0 else None
