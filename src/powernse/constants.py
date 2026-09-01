"""Shared frozen literals for PowerNSE."""

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/118.0"
NSE_HOME_URL = "https://www.nseindia.com/"
ARCHIVE_BASE_URL = "https://nsearchives.nseindia.com"
EQUITY_LIST_URL = f"{ARCHIVE_BASE_URL}/content/equities/EQUITY_L.csv"

BSE_HOME_URL = "https://www.bseindia.com/"
BSE_CORPORATE_ACTIONS_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w"
CORPORATE_ACTIONS_API_URL = "https://www.nseindia.com/api/corporates-corporateActions"
INDEX_CONSTITUENTS_API_URL = "https://www.nseindia.com/api/equity-stock-indices"
ALL_INDICES_API_URL = "https://www.nseindia.com/api/allIndices"
NSE_INDEX_HISTORY_API_URL = "https://www.nseindia.com/api/historicalOR/indicesHistory"
NSE_INDEX_HISTORY_REFERER = "https://www.nseindia.com/reports-indices-historical-index-data"
NIFTY_INDICES_HISTORY_URL = "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString"
NIFTY_INDICES_REFERER = "https://www.niftyindices.com/reports/historical-data"

# NSE's indicesHistory endpoint rejects windows wider than a year; deep pulls are chunked.
INDEX_HISTORY_MAX_CHUNK_DAYS = 365
# NIFTY 50 base date -- the earliest EOD index level NSE / NSE Indices publish.
INDEX_HISTORY_FROM_DATE = "1995-11-03"

# NSE switched CM bhavcopy naming on this calendar date (inclusive of new format).
UDIFF_SWITCH_DATE_ISO = "2024-07-08"

MIN_REQUEST_INTERVAL_SECONDS = 1.0 / 3.0
DEFAULT_SLEEP_SECONDS = 0.5
DEFAULT_ARCHIVE_DIRNAME = "nse-data"
ENV_ARCHIVE_ROOT = "POWERNSE_ROOT"
ENV_CACHE_DIR = "POWERNSE_CACHE_DIR"

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_HTTP_ATTEMPTS = 3

DEFAULT_INDEX_NAMES = ("NIFTY 50",)
DEFAULT_RESUME_DAYS = 100
EMPTY_ARCHIVE_FROM_DATE = "2000-01-01"
# Max days before OHLC window_start to scan staged CA JSON for ohlc_adjusted.
CA_ADJUSTMENT_LOOKBACK_DAYS = 365 * 5

ENV_GITHUB_REPO = "POWERNSE_GITHUB_REPO"
ENV_GITHUB_BRANCH = "POWERNSE_GITHUB_BRANCH"
DEFAULT_GITHUB_BRANCH = "main"
BUNDLE_ARCHIVE_SUBDIR = "nse-data"
