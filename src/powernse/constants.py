"""Shared frozen literals for PowerNSE."""

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/118.0"
NSE_HOME_URL = "https://www.nseindia.com/"
ARCHIVE_BASE_URL = "https://nsearchives.nseindia.com"
CORPORATE_ACTIONS_API_URL = "https://www.nseindia.com/api/corporates-corporateActions"
INDEX_CONSTITUENTS_API_URL = "https://www.nseindia.com/api/equity-stock-indices"

# NSE switched CM bhavcopy naming on this calendar date (inclusive of new format).
UDIFF_SWITCH_DATE_ISO = "2024-07-08"

MIN_REQUEST_INTERVAL_SECONDS = 1.0 / 3.0
DEFAULT_SLEEP_SECONDS = 0.5
DEFAULT_ARCHIVE_DIRNAME = "nse-data"
ENV_ARCHIVE_ROOT = "POWERNSE_ROOT"

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_HTTP_ATTEMPTS = 3

DEFAULT_INDEX_NAMES = ("NIFTY 50",)
DEFAULT_RESUME_DAYS = 100
EMPTY_ARCHIVE_FROM_DATE = "2000-01-01"

ENV_GITHUB_REPO = "POWERNSE_GITHUB_REPO"
ENV_GITHUB_BRANCH = "POWERNSE_GITHUB_BRANCH"
DEFAULT_GITHUB_BRANCH = "main"
BUNDLE_ARCHIVE_SUBDIR = "nse-data"

