"""Readers over a staged NSE archive -- the subsystem behind the NSEData facade."""

from powernse.reading.bhavcopy import BhavcopyReader
from powernse.reading.corporate import CorporateActionReader
from powernse.reading.coverage import CoverageReader
from powernse.reading.deals import DealsReader, SecbanReader
from powernse.reading.delivery import DeliveryReader
from powernse.reading.futures import FoReader
from powernse.reading.index import IndexReader
from powernse.reading.snapshots import SnapshotReader

__all__ = [
    "BhavcopyReader",
    "CorporateActionReader",
    "CoverageReader",
    "DealsReader",
    "DeliveryReader",
    "FoReader",
    "IndexReader",
    "SecbanReader",
    "SnapshotReader",
]
