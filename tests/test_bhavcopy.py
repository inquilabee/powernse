"""Critical tests for bhavcopy download staging and URL formats."""

import io
import json
import zipfile
from datetime import date
from pathlib import Path

from powernse.archive import manifest_path, sha256_file
from powernse.calendar import is_weekend
from powernse.downloaders.bhavcopy import (
    BhavcopyDownloader,
    bhavcopy_archive_url,
    staged_bhavcopy_csv_key,
    staged_bhavcopy_csv_path,
)


def test_bhavcopy_archive_url_legacy_format() -> None:
    url = bhavcopy_archive_url(date(2024, 1, 2))
    assert url.endswith("/cm02JAN2024bhav.csv.zip")
    assert "/historical/EQUITIES/2024/JAN/" in url


def test_bhavcopy_archive_url_udiff_format() -> None:
    url = bhavcopy_archive_url(date(2024, 8, 1))
    assert url.endswith("/BhavCopy_NSE_CM_0_0_0_20240801_F_0000.csv.zip")
    assert "/content/cm/" in url


def test_staged_bhavcopy_csv_path_layout() -> None:
    root = Path("/data/nse")
    path = staged_bhavcopy_csv_path(root, date(2024, 1, 2))
    assert path == root / "raw" / "bhavcopy" / "2024" / "2024-01-02.csv"


def test_is_weekend() -> None:
    assert is_weekend(date(2024, 1, 6)) is True
    assert is_weekend(date(2024, 1, 5)) is False


def _zip_bytes(csv_name: str, csv_body: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(csv_name, csv_body)
    return buffer.getvalue()


def test_downloader_stages_csv_and_manifest(tmp_path: Path) -> None:
    trade_date = date(2024, 1, 2)
    url = bhavcopy_archive_url(trade_date)
    payload = _zip_bytes("cm02JAN2024bhav.csv", "SYMBOL,SERIES\nRELIANCE,EQ\n")

    def fetch(_url: str) -> bytes:
        assert _url == url
        return payload

    downloader = BhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch)
    summary = downloader.download_range(trade_date, trade_date)

    staged = staged_bhavcopy_csv_path(tmp_path, trade_date)
    assert summary.downloaded_count == 1
    assert staged.read_text(encoding="utf-8").startswith("SYMBOL,SERIES")

    manifest = manifest_path(downloader.archive).read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest) == 1
    record = json.loads(manifest[0])
    assert record["url"] == url
    assert record["sha256"] == sha256_file(staged)
    assert record["local_path"] == staged_bhavcopy_csv_key(trade_date)


def test_downloader_skip_existing(tmp_path: Path) -> None:
    trade_date = date(2024, 1, 2)
    staged = staged_bhavcopy_csv_path(tmp_path, trade_date)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("SYMBOL,SERIES\nTCS,EQ\n", encoding="utf-8")

    def fetch(_url: str) -> bytes:
        raise AssertionError("should not fetch when skip_existing")

    downloader = BhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch, skip_existing=True)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary.downloaded_count == 0
    assert summary.skipped_existing_count == 1
