"""CLI smoke tests."""

from datetime import date
from pathlib import Path

from support import write_staged

from powernse.cli import main
from powernse.datasets import BHAVCOPY
from powernse.types import DownloadSummary

_BHAV = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,1,1,1,1,1\n"


def test_help_exits_zero() -> None:
    code = main(["--help"])
    assert code == 0


def test_status_empty_archive(tmp_path: Path) -> None:
    code = main(["status", "--root", str(tmp_path)])
    assert code == 0


def test_bhavcopy_cli_failed_days_soft_exit(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.root = tmp_path

        def download_range(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=0, skipped_existing_count=0, failed_count=2)

    monkeypatch.setattr("powernse.cli.app.BhavcopyDownloader", FakeDownloader)
    code = main(["bhavcopy", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path)])
    assert code == 0


def test_bhavcopy_cli_strict_exit_on_failures(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.root = tmp_path

        def download_range(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=0, skipped_existing_count=0, failed_count=2)

    monkeypatch.setattr("powernse.cli.app.BhavcopyDownloader", FakeDownloader)
    code = main(["bhavcopy", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path), "--strict"])
    assert code == 1


def test_bhavcopy_cli_success_exit(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.root = tmp_path

        def download_range(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=1, skipped_existing_count=0, failed_count=0)

    monkeypatch.setattr("powernse.cli.app.BhavcopyDownloader", FakeDownloader)
    code = main(["bhavcopy", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path)])
    assert code == 0


def test_verify_reports_gaps_and_exits_one(tmp_path: Path) -> None:
    write_staged(tmp_path, BHAVCOPY, date(2024, 1, 2), _BHAV)
    write_staged(tmp_path, BHAVCOPY, date(2024, 1, 4), _BHAV)
    code = main(["verify", "--dataset", "bhavcopy", "--root", str(tmp_path)])
    assert code == 1  # 2024-01-03 is a missing session


def test_verify_complete_dataset_exits_zero(tmp_path: Path) -> None:
    write_staged(tmp_path, BHAVCOPY, date(2024, 1, 2), _BHAV)
    code = main(
        ["verify", "--dataset", "bhavcopy", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path)]
    )
    assert code == 0


def test_verify_rejects_unknown_dataset(tmp_path: Path) -> None:
    code = main(["verify", "--dataset", "nope", "--root", str(tmp_path)])
    assert code != 0
