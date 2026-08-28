"""Download the NSE equity security master (``EQUITY_L.csv``)."""

from powernse.constants import EQUITY_LIST_URL
from powernse.datasets import EQUITY_LIST
from powernse.downloaders.deals import SnapshotCsvDownloader


class EquityListDownloader(SnapshotCsvDownloader):
    """Fetch the current ``EQUITY_L.csv`` and stage it under a label date."""

    dataset = EQUITY_LIST
    snapshot_url = EQUITY_LIST_URL
    snapshot_label = "Equity list"
