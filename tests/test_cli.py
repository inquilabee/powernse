"""CLI smoke tests."""

from pathlib import Path

from powernse.cli import main
from powernse.types import DownloadSummary


def test_help_exits_zero() -> None:
    code = main(["--help"])
    assert code == 0


def test_status_empty_archive(tmp_path: Path) -> None:
    code = main(["status", "--root", str(tmp_path)])
    assert code == 0


def test_bhavcopy_cli_failed_days_soft_exit(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *args, **kwargs) -> None:
            self.root = tmp_path

        def download_range(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=0, skipped_existing_count=0, failed_count=2)

    monkeypatch.setattr("powernse.cli.app.BhavcopyDownloader", FakeDownloader)
    code = main(["bhavcopy", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path)])
    assert code == 0


def test_bhavcopy_cli_strict_exit_on_failures(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *args, **kwargs) -> None:
            self.root = tmp_path

        def download_range(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=0, skipped_existing_count=0, failed_count=2)

    monkeypatch.setattr("powernse.cli.app.BhavcopyDownloader", FakeDownloader)
    code = main(
        ["bhavcopy", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path), "--strict"]
    )
    assert code == 1


def test_bhavcopy_cli_success_exit(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *args, **kwargs) -> None:
            self.root = tmp_path

        def download_range(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=1, skipped_existing_count=0, failed_count=0)

    monkeypatch.setattr("powernse.cli.app.BhavcopyDownloader", FakeDownloader)
    code = main(["bhavcopy", "--from", "2024-01-02", "--to", "2024-01-02", "--root", str(tmp_path)])
    assert code == 0
