"""Historical NSE index names, hand-maintained.

NSE has renamed most of its indices over the years (the broad ``S&P CNX`` /
``CNX`` families were rebranded ``NIFTY`` around November 2015), and the staged
``index_closes`` files carry whichever name was current on that date. NSE's
``/api/allIndices`` (the source for :mod:`powernse.index.catalog`) only knows
present-day names, so this map cannot be generated -- it is curated here and
merged into each :class:`~powernse.index.catalog.IndexEntry` at load time.

Keys are the catalog's canonical ``name``; values are earlier names seen in the
staged history (matched case-folded, so casing-only variants -- ``CNX PSE`` vs
``CNX Pse`` -- need only one entry). Not exhaustive: this is what turned up in a
2012-2026 ``ind_close_all`` pull plus the 1995-2012 ``index-history`` backfill.
"""

INDEX_ALIASES: dict[str, tuple[str, ...]] = {
    # -- broad market --------------------------------------------------------
    "NIFTY 50": ("CNX Nifty", "S&P CNX Nifty"),
    "NIFTY NEXT 50": ("CNX Nifty Junior",),
    "NIFTY 100": ("CNX 100",),
    "NIFTY 200": ("CNX 200",),
    "NIFTY 500": ("CNX 500", "S&P CNX 500"),
    "NIFTY MIDCAP 100": ("CNX Midcap",),
    "NIFTY MIDCAP 50": ("CNX Midcap 50",),
    "NIFTY SMALLCAP 100": ("CNX Smallcap",),
    "NIFTY50 DIVIDEND POINTS": ("CNX Nifty Dividend", "S&P CNX Nifty Dividend"),
    # -- sectoral (CNX -> NIFTY, Nov 2015) ---------------------------------
    "NIFTY BANK": ("CNX Bank", "Bank Nifty"),
    "NIFTY IT": ("CNX IT",),
    "NIFTY AUTO": ("CNX Auto",),
    "NIFTY ENERGY": ("CNX Energy",),
    "NIFTY FMCG": ("CNX FMCG",),
    "NIFTY FINANCIAL SERVICES": ("CNX Finance",),
    "NIFTY MEDIA": ("CNX Media",),
    "NIFTY METAL": ("CNX Metal",),
    "NIFTY PHARMA": ("CNX Pharma",),
    "NIFTY PSU BANK": ("CNX PSU Bank",),
    "NIFTY REALTY": ("CNX Realty",),
    # -- thematic ---------------------------------------------------------
    "NIFTY COMMODITIES": ("CNX Commodities",),
    "NIFTY INDIA CONSUMPTION": ("CNX Consumption",),
    "NIFTY DIVIDEND OPPORTUNITIES 50": ("CNX Dividend Opportunities", "CNX Dividend Oppt"),
    "NIFTY INFRASTRUCTURE": ("CNX Infrastructure", "CNX Infra"),
    "NIFTY MNC": ("CNX MNC",),
    "NIFTY PSE": ("CNX PSE",),
    "NIFTY SERVICES SECTOR": ("CNX Service Sector", "CNX Service"),
    # -- other ----------------------------------------------------------
    "INDIA VIX": ("India Vix",),
}
