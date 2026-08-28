"""BSE corporate-actions downloader + dividend parsing."""

import json
from datetime import date
from pathlib import Path

import pytest
from support import staged_path

from powernse.datasets import BSE_CORPORATE_ACTIONS
from powernse.downloaders.bse_corporate_actions import BseCorporateActionsDownloader, bse_exdate
from powernse.parsers.bse import parse_bse_dividend


@pytest.mark.parametrize(
    ("purpose", "expected"),
    [
        ("Final Dividend - Rs. - 1.1000", 1.1),
        ("Special Dividend - Rs. - 5.10", 5.1),
        ("Dividend - Rs. - 0.4000", 0.4),
        ("Interim Dividend - Rs. - 2", 2.0),
        ("Dividend - 30 %", None),  # percentage: face value not in the BSE row
        ("Rights Issue 1:2", None),
        ("Redemption of NCD", None),
    ],
)
def test_parse_bse_dividend(purpose: str, expected: float | None) -> None:
    assert parse_bse_dividend(purpose) == expected


def test_bse_exdate() -> None:
    assert bse_exdate({"exdate": "20240115"}) == date(2024, 1, 15)
    assert bse_exdate({"exdate": ""}) is None
    assert bse_exdate({"exdate": "2024011"}) is None
    assert bse_exdate({"exdate": "20241332"}) is None


def _row(symbol: str, exdate: str, purpose: str) -> dict[str, str]:
    return {"short_name": symbol, "exdate": exdate, "Ex_date": "x", "Purpose": purpose, "scrip_code": 1}


def test_download_buckets_rows_by_exdate(tmp_path: Path) -> None:
    payload = json.dumps(
        [
            _row("RELIANCE", "20240718", "Final Dividend - Rs. - 10.0000"),
            _row("TCS", "20240718", "Final Dividend - Rs. - 28.0000"),
            _row("INFY", "20240801", "Interim Dividend - Rs. - 6.0000"),
            _row("SKIP", "20250101", "out of the requested span"),
        ]
    ).encode()

    def fetch(url: str) -> bytes:
        assert "segment=Equity" in url
        assert "ddlcategorys=E" in url
        return payload

    downloader = BseCorporateActionsDownloader(tmp_path, sleep_seconds=0, skip_existing=True, fetch_bytes=fetch)
    summary = downloader.download_range(date(2024, 7, 1), date(2024, 8, 31))
    assert summary.downloaded_count == 2  # 2024-07-18 and 2024-08-01

    day1 = json.loads(staged_path(tmp_path, BSE_CORPORATE_ACTIONS, date(2024, 7, 18)).read_text(encoding="utf-8"))
    assert {r["short_name"] for r in day1} == {"RELIANCE", "TCS"}
    assert not staged_path(tmp_path, BSE_CORPORATE_ACTIONS, date(2025, 1, 1)).is_file()

    # re-run: everything already staged for 2024 -> nothing downloaded
    again = downloader.download_range(date(2024, 7, 1), date(2024, 8, 31))
    assert again.downloaded_count == 0
