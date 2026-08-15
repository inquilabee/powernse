"""Small shared value types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DownloadSummary:
    """Counts from a download run."""

    downloaded_count: int
    skipped_existing_count: int
    failed_count: int = 0

    @property
    def total_considered(self) -> int:
        return self.downloaded_count + self.skipped_existing_count + self.failed_count
