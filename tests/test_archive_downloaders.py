"""Tests for F&O, index closes, full bhavcopy, and deals downloaders."""

from datetime import date
from pathlib import Path

from support import staged_path, zip_bytes

from powernse.datasets import BULK_DEALS, FO_BHAVCOPY, FULL_BHAVCOPY, INDEX_CLOSES
from powernse.downloaders.deals import BULK_DEALS_URL, BulkDealsDownloader
from powernse.downloaders.fo_bhavcopy import FoBhavcopyDownloader
from powernse.downloaders.full_bhavcopy import FullBhavcopyDownloader
from powernse.downloaders.index_closes import IndexClosesDownloader


def test_fo_bhavcopy_url_and_stage(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 9)
    url = FoBhavcopyDownloader.archive_url(trade_date)
    assert url.endswith("BhavCopy_NSE_FO_0_0_0_20240809_F_0000.csv.zip")
    legacy = FoBhavcopyDownloader.archive_url(date(2024, 1, 2))
    assert "/content/historical/DERIVATIVES/2024/JAN/fo02JAN2024bhav.csv.zip" in legacy
    payload = zip_bytes(("BhavCopy_NSE_FO_0_0_0_20240809_F_0000.csv", "TckrSymb,ClsPric\nRELIANCE,100\n"))

    def fetch(fetched: str) -> bytes:
        assert fetched == url
        return payload

    downloader = FoBhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch)
    summary = downloader.download_range(trade_date, trade_date)
    assert summary.downloaded_count == 1
    assert staged_path(tmp_path, FO_BHAVCOPY, trade_date).read_text(encoding="utf-8").startswith("TckrSymb")


def test_index_closes_and_full_bhavcopy(tmp_path: Path) -> None:
    trade_date = date(2024, 8, 9)
    assert "ind_close_all_09082024.csv" in IndexClosesDownloader.archive_url(trade_date)
    assert "sec_bhavdata_full_09082024.csv" in FullBhavcopyDownloader.archive_url(trade_date)

    def fetch_index(url: str) -> bytes:
        assert "ind_close_all" in url
        return b"Index Name,Closing Index Value\nNifty 50,24000\n"

    def fetch_full(url: str) -> bytes:
        assert "sec_bhavdata_full" in url
        return b"SYMBOL,CLOSE_PRICE,DELIV_QTY\nRELIANCE,100,10\n"

    IndexClosesDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch_index).download_range(trade_date, trade_date)
    FullBhavcopyDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch_full).download_range(trade_date, trade_date)
    assert staged_path(tmp_path, INDEX_CLOSES, trade_date).is_file()
    assert staged_path(tmp_path, FULL_BHAVCOPY, trade_date).is_file()


def test_bulk_deals_snapshot_labeled(tmp_path: Path) -> None:
    label = date(2024, 8, 9)

    def fetch(url: str) -> bytes:
        assert url == BULK_DEALS_URL
        return b"Date,Symbol\n09-AUG-2024,RELIANCE\n"

    summary = BulkDealsDownloader(tmp_path, sleep_seconds=0, fetch_bytes=fetch).download(label)
    assert summary.downloaded_count == 1
    assert staged_path(tmp_path, BULK_DEALS, label).read_text(encoding="utf-8").startswith("Date,Symbol")
