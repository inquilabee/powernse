"""PowerNSE — download and use official NSE India equity archives."""

from importlib.metadata import PackageNotFoundError, version

from powernse.archive import ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.data import NSEData
from powernse.downloaders import (
    BhavcopyDownloader,
    CorporateActionsDownloader,
    FoBhavcopyDownloader,
    FullBhavcopyDownloader,
    IndexClosesDownloader,
    IndexConstituentsDownloader,
    bhavcopy_archive_url,
)
from powernse.errors import ArchiveError, DownloadError, PayloadError, PowerNseError
from powernse.loaders import ArchiveReader
from powernse.settings import Settings
from powernse.types import AdjustedOhlcBar, DownloadSummary, FoBar, IndexBar, OhlcBar

__all__ = [
    "ArchiveError",
    "ArchiveReader",
    "ArchiveRoot",
    "AdjustedOhlcBar",
    "BhavcopyDownloader",
    "CorporateActionsDownloader",
    "DownloadError",
    "DownloadSummary",
    "FoBar",
    "FoBhavcopyDownloader",
    "FullBhavcopyDownloader",
    "IndexBar",
    "IndexClosesDownloader",
    "IndexConstituentsDownloader",
    "NSEData",
    "OhlcBar",
    "PayloadError",
    "PowerNseError",
    "Settings",
    "bhavcopy_archive_url",
    "iter_trading_dates",
]


def package_version() -> str:
    try:
        return version("powernse")
    except PackageNotFoundError:
        return "0.0.0+local"


__version__ = package_version()
