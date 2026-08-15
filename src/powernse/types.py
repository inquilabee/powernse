"""Small shared value types."""

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class DownloadSummary:
    """Counts from a download run."""

    downloaded_count: int
    skipped_existing_count: int
    failed_count: int = 0

    @property
    def total_considered(self) -> int:
        return self.downloaded_count + self.skipped_existing_count + self.failed_count

    def __add__(self, other: Self) -> Self:
        if not isinstance(other, DownloadSummary):
            return NotImplemented
        return type(self)(
            downloaded_count=self.downloaded_count + other.downloaded_count,
            skipped_existing_count=self.skipped_existing_count + other.skipped_existing_count,
            failed_count=self.failed_count + other.failed_count,
        )
