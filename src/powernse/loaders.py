"""Compatibility reader — prefer ``NSEData``.

Kept as a thin alias until a future minor version removes it from the package front.
"""

from powernse.data import NSEData

ArchiveReader = NSEData
