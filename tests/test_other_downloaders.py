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
from powernse.settings import Settings
from powernse.types import DownloadSummary


def test_corporate_actions_url_shape() -> None:
    url = corporate_actions_request_url(date(2024, 8, 1), date(2024, 8, 1))
    assert "corporates-corporateActions" in url
    assert "from_date=01-08-2024" in url


def test_corporate_actions_invalid_json_non_strict(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 1)

    def fetch(_url: str) -> bytes:
        return b"<html>not json</html>"

    downloader = CorporateActionsDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch, strict=False)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary == DownloadSummary(downloaded_count=0, skipped_existing_count=0, failed_count=1)
    assert not corporate_actions_staged_path(tmp_path, trade_date).is_file()


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


def test_settings_env_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POWERNSE_ROOT", str(tmp_path / "from-env"))
    settings = Settings.resolve(None)
    assert settings.archive_root == (tmp_path / "from-env").resolve()


def test_download_summary_add() -> None:
    left = DownloadSummary(1, 2, 3)
    right = DownloadSummary(4, 5, 6)
    assert left + right == DownloadSummary(5, 7, 9)
