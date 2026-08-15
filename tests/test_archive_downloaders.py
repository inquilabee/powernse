"""Tests for F&O, index closes, full bhavcopy, and deals downloaders."""

import io
import zipfile
from datetime import date
from pathlib import Path

from powernse.downloaders.deals import (
    BULK_DEALS_URL,
    BulkDealsDownloader,
    staged_bulk_deals_csv_path,
)
from powernse.downloaders.fo_bhavcopy import (
    FoBhavcopyDownloader,
    fo_bhavcopy_archive_url,
    staged_fo_bhavcopy_csv_path,
)
from powernse.downloaders.full_bhavcopy import (
    FullBhavcopyDownloader,
    full_bhavcopy_archive_url,
    staged_full_bhavcopy_csv_path,
)
from powernse.downloaders.index_closes import (
    IndexClosesDownloader,
    index_closes_archive_url,
    staged_index_closes_csv_path,
)


def _zip_bytes(name: str, body: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, body)
    return buffer.getvalue()


def test_fo_bhavcopy_url_and_stage(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 9)
    url = fo_bhavcopy_archive_url(trade_date)
    assert url.endswith("BhavCopy_NSE_FO_0_0_0_20240809_F_0000.csv.zip")
    payload = _zip_bytes("BhavCopy_NSE_FO_0_0_0_20240809_F_0000.csv", "TckrSymb,ClsPric\nRELIANCE,100\n")

    def fetch(fetched: str) -> bytes:
        assert fetched == url
        return payload

    downloader = FoBhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary.downloaded_count == 1
    assert staged_fo_bhavcopy_csv_path(tmp_path, trade_date).read_text(encoding="utf-8").startswith("TckrSymb")


def test_index_closes_and_full_bhavcopy(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 9)
    assert "ind_close_all_09082024.csv" in index_closes_archive_url(trade_date)
    assert "sec_bhavdata_full_09082024.csv" in full_bhavcopy_archive_url(trade_date)

    def fetch_index(url: str) -> bytes:
        assert "ind_close_all" in url
        return b"Index Name,Closing Index Value\nNifty 50,24000\n"

    def fetch_full(url: str) -> bytes:
        assert "sec_bhavdata_full" in url
        return b"SYMBOL,CLOSE_PRICE,DELIV_QTY\nRELIANCE,100,10\n"

    IndexClosesDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch_index).download_range(trade_date, trade_date)
    FullBhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch_full).download_range(trade_date, trade_date)
    assert staged_index_closes_csv_path(tmp_path, trade_date).is_file()
    assert staged_full_bhavcopy_csv_path(tmp_path, trade_date).is_file()


def test_bulk_deals_snapshot_labeled(tmp_path: Path) -> None:
    label = date(2024, 8, 9)

    def fetch(url: str) -> bytes:
        assert url == BULK_DEALS_URL
        return b"Date,Symbol\n09-AUG-2024,RELIANCE\n"

    summary = BulkDealsDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch).download(label)
    assert summary.downloaded_count == 1
    assert staged_bulk_deals_csv_path(tmp_path, label).read_text(encoding="utf-8").startswith("Date,Symbol")
