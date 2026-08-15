"""Critical tests for bhavcopy download staging and URL formats."""

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest
import requests

from powernse.archive import manifest_path, sha256_file
from powernse.calendar import is_weekend, iter_trading_dates
from powernse.downloaders.bhavcopy import (
    BhavcopyDownloader,
    bhavcopy_archive_url,
    extract_zip_payload_to_csv_bytes,
    staged_bhavcopy_csv_key,
    staged_bhavcopy_csv_path,
)
from powernse.errors import DownloadError, PayloadError
from powernse.http import NseHttpClient, RequestThrottler
from powernse.loaders import ArchiveReader


def test_bhavcopy_archive_url_legacy_format() -> None:
    url = bhavcopy_archive_url(date(2024, 1, 2))
    assert url.endswith("/cm02JAN2024bhav.csv.zip")
    assert "/historical/EQUITIES/2024/JAN/" in url


def test_bhavcopy_archive_url_udiff_format() -> None:
    url = bhavcopy_archive_url(date(2024, 8, 1))
    assert url.endswith("/BhavCopy_NSE_CM_0_0_0_20240801_F_0000.csv.zip")
    assert "/content/cm/" in url


def test_bhavcopy_archive_url_udiff_switch_boundary() -> None:
    assert "BhavCopy_NSE_CM" in bhavcopy_archive_url(date(2024, 7, 8))
    assert "cm05JUL2024bhav" in bhavcopy_archive_url(date(2024, 7, 5))


def test_staged_bhavcopy_csv_path_layout() -> None:
    root = Path("/data/nse")
    path = staged_bhavcopy_csv_path(root, date(2024, 1, 2))
    assert path == root / "raw" / "bhavcopy" / "2024" / "2024-01-02.csv"


def test_is_weekend() -> None:
    assert is_weekend(date(2024, 1, 6)) is True
    assert is_weekend(date(2024, 1, 5)) is False


def test_all_calendar_days_includes_weekend() -> None:
    days = list(iter_trading_dates(date(2024, 1, 5), date(2024, 1, 7), all_calendar_days=True))
    assert date(2024, 1, 6) in days
    sessions_only = list(iter_trading_dates(date(2024, 1, 5), date(2024, 1, 7), all_calendar_days=False))
    assert date(2024, 1, 6) not in sessions_only


def _zip_bytes(*members: tuple[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in members:
            archive.writestr(name, body)
    return buffer.getvalue()


def test_downloader_stages_csv_and_manifest(tmp_path: Path) -> None:
    trade_date = date(2024, 1, 2)
    url = bhavcopy_archive_url(trade_date)
    payload = _zip_bytes(("cm02JAN2024bhav.csv", "SYMBOL,SERIES\nRELIANCE,EQ\n"))

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

    rows = ArchiveReader(tmp_path).bhavcopy_rows(trade_date)
    assert rows[0]["SYMBOL"] == "RELIANCE"


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


def test_non_strict_maps_download_error(tmp_path: Path) -> None:
    trade_date = date(2024, 1, 2)

    def fetch(_url: str) -> bytes:
        raise DownloadError("boom")

    downloader = BhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch, strict=False)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary.failed_count == 1


def test_strict_raises_download_error(tmp_path: Path) -> None:
    trade_date = date(2024, 1, 2)

    def fetch(_url: str) -> bytes:
        raise DownloadError("boom")

    downloader = BhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch, strict=True)
    with pytest.raises(DownloadError):
        downloader.download_range(trade_date, trade_date)


def test_http_client_wraps_http_error() -> None:
    class FakeResponse:
        status_code = 404
        headers: dict[str, str] = {}
        content = b"missing"

        def raise_for_status(self) -> None:
            error = requests.HTTPError("404")
            error.response = self  # type: ignore[assignment]
            raise error

    class FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

    client = NseHttpClient(session=FakeSession(), min_interval_seconds=0)  # type: ignore[arg-type]
    client._primed = True
    with pytest.raises(DownloadError, match="HTTP 404"):
        client.fetch_bytes("https://example.test/missing")


def test_throttler_enforces_minimum_interval() -> None:
    throttler = RequestThrottler(0.05)
    start = __import__("time").monotonic()
    throttler.wait()
    throttler.wait()
    elapsed = __import__("time").monotonic() - start
    assert elapsed >= 0.05


def test_extract_zip_rejects_ambiguous_members() -> None:
    payload = _zip_bytes(("a.csv", "a"), ("b.csv", "b"))
    with pytest.raises(PayloadError, match="Ambiguous"):
        extract_zip_payload_to_csv_bytes(payload)
