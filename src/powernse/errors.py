"""Domain errors for PowerNSE."""


class PowerNseError(Exception):
    """Base error for the package."""


class DownloadError(PowerNseError):
    """Raised when an NSE archive or API payload cannot be downloaded."""


class ArchiveError(PowerNseError):
    """Raised when local archive layout or paths are invalid."""


class PayloadError(PowerNseError):
    """Raised when a downloaded payload cannot be parsed or extracted."""
