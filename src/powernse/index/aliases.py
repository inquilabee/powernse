"""Historical NSE index names, hand-maintained.

NSE has renamed several flagship indices over the years, and the staged
``index_closes`` files carry whichever name was current on that date. NSE's
``/api/allIndices`` (the source for :mod:`powernse.index.catalog`) only knows
present-day names, so this map cannot be generated -- it is curated here and
merged into each :class:`~powernse.index.catalog.IndexEntry` at load time.

Keys are the catalog's canonical ``name``; values are earlier names seen in
``ind_close_all_*.csv`` (case-folded when matched, so casing-only differences do
not need an entry -- ``India Vix`` is listed for clarity only). Not exhaustive:
this is what turned up in a 2012-2026 pull.
"""

INDEX_ALIASES: dict[str, tuple[str, ...]] = {
    "NIFTY 50": ("CNX Nifty", "S&P CNX Nifty"),
    "NIFTY NEXT 50": ("CNX Nifty Junior",),
    "NIFTY 100": ("CNX 100",),
    "NIFTY 200": ("CNX 200",),
    "NIFTY 500": ("CNX 500", "S&P CNX 500"),
    "NIFTY MIDCAP 100": ("CNX Midcap",),
    "NIFTY MIDCAP 50": ("CNX Midcap 50",),
    "NIFTY BANK": ("CNX Bank", "Bank Nifty"),
    "NIFTY IT": ("CNX IT",),
    "INDIA VIX": ("India Vix",),
}
