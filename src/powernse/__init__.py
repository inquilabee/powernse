"""PowerNSE — download and use NSE India end-of-day equity archives."""

from importlib.metadata import PackageNotFoundError, version

from powernse.archive import ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.corporate_actions import CorporateActions, CorporateActionType, SubjectClassifier
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
from powernse.schemas import AdjustedOhlcSchema, FoSchema, IndexSchema, OhlcSchema
from powernse.settings import Settings
from powernse.types import DownloadSummary

__all__ = [
    "AdjustedOhlcSchema",
    "ArchiveError",
    "ArchiveRoot",
    "BhavcopyDownloader",
    "BlockDealsDownloader",
    "BulkDealsDownloader",
    "CorporateActions",
    "CorporateActionsDownloader",
    "CorporateActionType",
    "DownloadError",
    "DownloadSummary",
    "FoBhavcopyDownloader",
    "FoSchema",
    "FoSecbanDownloader",
    "FullBhavcopyDownloader",
    "IndexClosesDownloader",
    "IndexConstituentsDownloader",
    "IndexSchema",
    "NSEData",
    "OhlcSchema",
    "PayloadError",
    "PowerNseError",
    "Settings",
    "SubjectClassifier",
    "iter_trading_dates",
]


def package_version() -> str:
    try:
        return version("powernse")
    except PackageNotFoundError:
        return "0.0.0+local"


__version__ = package_version()
