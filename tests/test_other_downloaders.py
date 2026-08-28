"""Corporate actions and index constituents downloader tests."""

import json
from datetime import date
from pathlib import Path

from support import staged_path

from powernse.data import NSEData
from powernse.datasets import CORPORATE_ACTIONS, INDEX_CONSTITUENTS
from powernse.downloaders.corporate_actions import CorporateActionsDownloader
from powernse.downloaders.index_constituents import (
    IndexConstituentsDownloader,
    index_slug,
    parse_index_constituent_symbols,
)
from powernse.settings import Settings
from powernse.types import DownloadSummary


def test_corporate_actions_url_shape() -> None:
    url = CorporateActionsDownloader.request_url(date(2024, 8, 1), date(2024, 8, 1))
    assert "corporates-corporateActions" in url
    assert "from_date=01-08-2024" in url


def test_corporate_actions_download(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 1)
    payload = json.dumps([{"symbol": "RELIANCE", "subject": "Dividend", "exDate": "2024-08-01"}]).encode()

    def fetch(url: str) -> bytes:
        assert "01-08-2024" in url
        return payload

    downloader = CorporateActionsDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary.downloaded_count == 1
    path = staged_path(tmp_path, CORPORATE_ACTIONS, trade_date)
    assert json.loads(path.read_text(encoding="utf-8"))[0]["symbol"] == "RELIANCE"
    got = NSEData(tmp_path).actions_for("RELIANCE", from_date=trade_date, to_date=trade_date)
    assert got[0]["symbol"] == "RELIANCE"


def test_corporate_actions_invalid_json_non_strict(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 1)

    def fetch(_url: str) -> bytes:
        return b"<html>not json</html>"

    downloader = CorporateActionsDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch, strict=False)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary == DownloadSummary(downloaded_count=0, skipped_existing_count=0, failed_count=1)
    assert not staged_path(tmp_path, CORPORATE_ACTIONS, trade_date).is_file()


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
    path = staged_path(tmp_path, INDEX_CONSTITUENTS, trade_date, discriminator=index_slug("NIFTY 50"))
    assert path.is_file()

    reader = NSEData(tmp_path)
    assert reader.index("NIFTY 50").symbols(trade_date) == ["RELIANCE"]
    inv = reader.inventory()
    assert inv["index_constituents"] == 1


def test_index_constituents_url() -> None:
    url = IndexConstituentsDownloader.request_url("NIFTY 50")
    assert "equity-stock-indices" in url


def test_settings_env_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POWERNSE_ROOT", str(tmp_path / "from-env"))
    settings = Settings.resolve(None)
    assert settings.archive_root == (tmp_path / "from-env").resolve()


def test_download_summary_add() -> None:
    left = DownloadSummary(1, 2, 3)
    right = DownloadSummary(4, 5, 6)
    assert left + right == DownloadSummary(5, 7, 9)
