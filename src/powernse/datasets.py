"""The staged NSE archives PowerNSE knows how to download and read.

One :class:`Dataset` per archive family. It owns the on-disk shape only -- the
folder under ``raw/`` and the staged file name for a given day. Remote-source
logic lives on the downloaders; schema/parsing lives on the readers.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

_RAW = Path("raw")


@dataclass(frozen=True, slots=True)
class Dataset:
    """A staged archive family: its ``raw/`` sub-tree and staged-file naming.

    ``discriminator`` covers the one family (index constituents) that stages more
    than one file per day -- ``2024-01-02_nifty_50.json`` rather than
    ``2024-01-02.json``.
    """

    key: str
    extension: str

    def __str__(self) -> str:
        return self.key

    @property
    def raw_dir(self) -> Path:
        return _RAW / self.key

    def relpath(self, day: date, *, discriminator: str = "") -> Path:
        """Archive-relative path for one staged day (optionally discriminated)."""
        stem = f"{day.isoformat()}_{discriminator}" if discriminator else day.isoformat()
        return self.raw_dir / str(day.year) / f"{stem}.{self.extension}"

    def date_of(self, staged: Path) -> date | None:
        """The staged day parsed from a file name, or ``None`` if it doesn't match."""
        if staged.suffix != f".{self.extension}":
            return None
        try:
            return date.fromisoformat(staged.stem[:10])
        except ValueError:
            return None


BHAVCOPY = Dataset("bhavcopy", "csv")
FO_BHAVCOPY = Dataset("fo_bhavcopy", "csv")
FULL_BHAVCOPY = Dataset("full_bhavcopy", "csv")
INDEX_CLOSES = Dataset("index_closes", "csv")
BULK_DEALS = Dataset("bulk_deals", "csv")
BLOCK_DEALS = Dataset("block_deals", "csv")
FO_SECBAN = Dataset("fo_secban", "csv")
CORPORATE_ACTIONS = Dataset("corporate_actions", "json")
INDEX_CONSTITUENTS = Dataset("index_constituents", "json")

ALL: tuple[Dataset, ...] = (
    BHAVCOPY,
    FO_BHAVCOPY,
    FULL_BHAVCOPY,
    INDEX_CLOSES,
    BULK_DEALS,
    BLOCK_DEALS,
    FO_SECBAN,
    CORPORATE_ACTIONS,
    INDEX_CONSTITUENTS,
)
