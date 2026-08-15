"""Tests for bhavcopy --resume range resolution."""

from datetime import date
from pathlib import Path

import pytest

from powernse.cli import main
from powernse.downloaders.bhavcopy import (
    EMPTY_ARCHIVE_FROM,
    latest_staged_bhavcopy_date,
    resolve_bhavcopy_resume_range,
    staged_bhavcopy_csv_path,
)
from powernse.types import DownloadSummary


def test_latest_staged_bhavcopy_date_empty(tmp_path: Path) -> None:
    assert latest_staged_bhavcopy_date(tmp_path) is None


def test_latest_staged_bhavcopy_date_picks_max(tmp_path: Path) -> None:
    for day in (date(2024, 8, 1), date(2024, 8, 5), date(2023, 12, 29)):
        path = staged_bhavcopy_csv_path(tmp_path, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("SYMBOL,SERIES\n", encoding="utf-8")
    assert latest_staged_bhavcopy_date(tmp_path) == date(2024, 8, 5)


def test_resume_empty_archive_uses_epoch_then_days_cap(tmp_path: Path) -> None:
    today = date(2024, 8, 15)
    resolved_from, resolved_to = resolve_bhavcopy_resume_range(tmp_path, today=today, days=100)
    assert resolved_to == today
    assert resolved_from == date(2024, 5, 7)  # today - 100 days
    assert EMPTY_ARCHIVE_FROM == date(2000, 1, 1)


def test_resume_from_last_staged_within_days(tmp_path: Path) -> None:
    last = date(2024, 8, 10)
    path = staged_bhavcopy_csv_path(tmp_path, last)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("SYMBOL,SERIES\n", encoding="utf-8")
    today = date(2024, 8, 15)
    resolved_from, resolved_to = resolve_bhavcopy_resume_range(tmp_path, today=today, days=100)
    assert resolved_from == last
    assert resolved_to == today


def test_resume_clamps_old_last_to_days(tmp_path: Path) -> None:
    last = date(2020, 1, 1)
    path = staged_bhavcopy_csv_path(tmp_path, last)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("SYMBOL,SERIES\n", encoding="utf-8")
    today = date(2024, 8, 15)
    resolved_from, resolved_to = resolve_bhavcopy_resume_range(tmp_path, today=today, days=30)
    assert resolved_from == date(2024, 7, 16)
    assert resolved_to == today


def test_resume_rejects_non_positive_days(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--days"):
        resolve_bhavcopy_resume_range(tmp_path, days=0)


def test_bhavcopy_resume_cli(tmp_path: Path, monkeypatch) -> None:
    from powernse import cli

    captured: dict[str, date] = {}

    class FakeDownloader:
        def __init__(self, *args, **kwargs) -> None:
            self.root = tmp_path

        def download_range(self, from_date: date, to_date: date) -> DownloadSummary:
            captured["from"] = from_date
            captured["to"] = to_date
            return DownloadSummary(1, 0, 0)

    def fake_resolve(root, *, today=None, days=100, from_date=None, to_date=None):
        del root, today, days, from_date, to_date
        return date(2024, 8, 10), date(2024, 8, 15)

    monkeypatch.setattr(cli, "BhavcopyDownloader", FakeDownloader)
    monkeypatch.setattr(cli, "resolve_bhavcopy_resume_range", fake_resolve)
    code = main(["bhavcopy", "--resume", "--root", str(tmp_path)])
    assert code == 0
    assert captured["from"] == date(2024, 8, 10)
    assert captured["to"] == date(2024, 8, 15)


def test_bhavcopy_requires_from_to_without_resume(tmp_path: Path) -> None:
    code = main(["bhavcopy", "--root", str(tmp_path)])
    assert code == 2
