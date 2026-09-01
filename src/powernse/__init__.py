"""PowerNSE — download and use NSE India end-of-day equity archives."""

from importlib.metadata import PackageNotFoundError, version

from powernse.archive import ArchiveRoot
from powernse.calendar import iter_trading_dates
from powernse.corporate_actions import (
    CorporateActions,
    CorporateActionType,
    PriceAnomaly,
    RightsTerms,
    SkippedEvent,
    SubjectClassifier,
)
from powernse.data import NSEData
from powernse.downloaders import (
    BhavcopyDownloader,
    BlockDealsDownloader,
    BseCorporateActionsDownloader,
    BulkDealsDownloader,
    CorporateActionsDownloader,
    EquityListDownloader,
    FoBhavcopyDownloader,
    FoSecbanDownloader,
    FullBhavcopyDownloader,
    IndexClosesDownloader,
    IndexConstituentsDownloader,
    IndexHistoryDownloader,
)
from powernse.errors import ArchiveError, DownloadError, PayloadError, PowerNseError
from powernse.index import Index
from powernse.schemas import (
    AdjustedOhlcSchema,
    DealSchema,
    DeliverySchema,
    FoSchema,
    IndexSchema,
    OhlcSchema,
    SecuritySchema,
)
from powernse.settings import Settings
from powernse.types import DownloadSummary

__all__ = [
    "AdjustedOhlcSchema",
    "ArchiveError",
    "ArchiveRoot",
    "BhavcopyDownloader",
    "BlockDealsDownloader",
    "BseCorporateActionsDownloader",
    "BulkDealsDownloader",
    "CorporateActions",
    "CorporateActionsDownloader",
    "CorporateActionType",
    "DealSchema",
    "DeliverySchema",
    "DownloadError",
    "DownloadSummary",
    "EquityListDownloader",
    "FoBhavcopyDownloader",
    "FoSchema",
    "FoSecbanDownloader",
    "FullBhavcopyDownloader",
    "IndexClosesDownloader",
    "IndexConstituentsDownloader",
    "IndexHistoryDownloader",
    "Index",
    "IndexSchema",
    "NSEData",
    "OhlcSchema",
    "PayloadError",
    "PowerNseError",
    "PriceAnomaly",
    "RightsTerms",
    "SecuritySchema",
    "SkippedEvent",
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
