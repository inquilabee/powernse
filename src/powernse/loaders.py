"""Compatibility reader — prefer ``NSEData``."""

from powernse.data import NSEData


class ArchiveReader(NSEData):
    """Thin alias for ``NSEData`` kept for existing imports."""
