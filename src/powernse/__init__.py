"""PowerNSE — download and use official NSE India equity archives."""

from powernse.archive import ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.downloaders import (
    BhavcopyDownloader,
    CorporateActionsDownloader,
    IndexConstituentsDownloader,
    bhavcopy_archive_url,
)
from powernse.errors import ArchiveError, DownloadError, PayloadError, PowerNseError
from powernse.loaders import ArchiveReader
from powernse.settings import Settings
from powernse.types import DownloadSummary

__all__ = [
    "ArchiveError",
    "ArchiveReader",
    "ArchiveRoot",
    "BhavcopyDownloader",
    "CorporateActionsDownloader",
    "DownloadError",
    "DownloadSummary",
    "IndexConstituentsDownloader",
    "PayloadError",
    "PowerNseError",
    "Settings",
    "bhavcopy_archive_url",
    "iter_trading_dates",
]

__version__ = "0.1.0"
