"""Corporate actions and index constituents downloader tests."""

import json
from datetime import date
from pathlib import Path

from powernse.downloaders.corporate_actions import (
    CorporateActionsDownloader,
    corporate_actions_request_url,
    corporate_actions_staged_path,
)
from powernse.downloaders.index_constituents import (
    IndexConstituentsDownloader,
    index_constituents_request_url,
    index_constituents_staged_path,
    parse_index_constituent_symbols,
)
from powernse.loaders import ArchiveReader


def test_corporate_actions_url_shape() -> None:
    url = corporate_actions_request_url(date(2024, 8, 1), date(2024, 8, 1))
    assert "corporates-corporateActions" in url
    assert "from_date=01-08-2024" in url


def test_corporate_actions_download(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 1)
    payload = json.dumps([{"symbol": "RELIANCE", "subject": "Dividend"}]).encode()

    def fetch(url: str) -> bytes:
        assert "01-08-2024" in url
        return payload

    downloader = CorporateActionsDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary.downloaded_count == 1
    path = corporate_actions_staged_path(tmp_path, trade_date)
    assert json.loads(path.read_text(encoding="utf-8"))[0]["symbol"] == "RELIANCE"


def test_index_constituents_parse_and_download(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 5)
    payload = json.dumps(
        {
            "data": [
                {"symbol": "RELIANCE", "series": "EQ"},
                {"symbol": "SKIP", "series": "BE"},
            ]
        }
    ).encode()
    assert parse_index_constituent_symbols(payload) == ["RELIANCE"]

    def fetch(url: str) -> bytes:
        assert "equity-stock-indices" in url
        assert "NIFTY+50" in url or "NIFTY%2050" in url
        return payload

    downloader = IndexConstituentsDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch)
    summary = downloader.download_indices(trade_date, ["NIFTY 50"])
    assert summary.downloaded_count == 1
    path = index_constituents_staged_path(tmp_path, trade_date, "NIFTY 50")
    assert path.is_file()

    reader = ArchiveReader(tmp_path)
    assert reader.index_symbols(trade_date, "NIFTY 50") == ["RELIANCE"]
    inv = reader.inventory()
    assert inv["index_constituents"] == 1


def test_index_constituents_url() -> None:
    url = index_constituents_request_url("NIFTY 50")
    assert "equity-stock-indices" in url
