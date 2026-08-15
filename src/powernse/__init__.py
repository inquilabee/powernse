"""PowerNSE — download and use NSE India end-of-day equity archives."""

from importlib.metadata import PackageNotFoundError, version

from powernse.archive import ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.data import NSEData
from powernse.downloaders import (
    BhavcopyDownloader,
    BlockDealsDownloader,
    BulkDealsDownloader,
    CorporateActionsDownloader,
    FoBhavcopyDownloader,
    FoSecbanDownloader,
    FullBhavcopyDownloader,
    IndexClosesDownloader,
    IndexConstituentsDownloader,
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
    "BlockDealsDownloader",
    "BulkDealsDownloader",
    "CorporateActionsDownloader",
    "DownloadError",
    "DownloadSummary",
    "FoBar",
    "FoBhavcopyDownloader",
    "FoSecbanDownloader",
    "FullBhavcopyDownloader",
    "IndexBar",
    "IndexClosesDownloader",
    "IndexConstituentsDownloader",
    "NSEData",
    "OhlcBar",
    "PayloadError",
    "PowerNseError",
    "Settings",
    "iter_trading_dates",
]


def package_version() -> str:
    try:
        return version("powernse")
    except PackageNotFoundError:
        return "0.0.0+local"


__version__ = package_version()
