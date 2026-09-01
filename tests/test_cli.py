"""CLI smoke tests."""

from datetime import date
from pathlib import Path

from support import write_staged

from powernse.cli import main
from powernse.datasets import BHAVCOPY, EQUITY_LIST
from powernse.types import DownloadSummary

_BHAV = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nRELIANCE,EQ,1,1,1,1,1\n"
_EQUITY_L = (
    "SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\n"
    "RELIANCE, Reliance Industries Limited, EQ, 29-NOV-1995, 10, 1, INE002A01018, 10\n"
)


def test_help_exits_zero() -> None:
    code = main(["--help"])
    assert code == 0


def test_version_prints_installed_version(capsys) -> None:
    from powernse import package_version

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == package_version()


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


def test_anomalies_cli_flags_unexplained(tmp_path: Path, capsys) -> None:
    body = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nETF,EQ,{c},{c},{c},{c},1000\n"
    for day, close in ((date(2020, 1, 6), 1000.0), (date(2020, 1, 7), 1010.0), (date(2020, 1, 8), 101.0)):
        write_staged(tmp_path, BHAVCOPY, day, body.format(c=close))
    code = main(["anomalies", "ETF", "--from", "2020-01-01", "--to", "2020-01-31", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "2020-01-08" in out and "UNEXPLAINED" in out


def test_anomalies_cli_quiet_when_none(tmp_path: Path) -> None:
    body = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\nETF,EQ,{c},{c},{c},{c},1000\n"
    for day, close in ((date(2020, 1, 6), 100.0), (date(2020, 1, 7), 101.0)):
        write_staged(tmp_path, BHAVCOPY, day, body.format(c=close))
    code = main(["anomalies", "ETF", "--from", "2020-01-01", "--to", "2020-01-31", "--root", str(tmp_path)])
    assert code == 0


def test_securities_read_by_symbol(tmp_path: Path, capsys) -> None:
    write_staged(tmp_path, EQUITY_LIST, date(2024, 8, 1), _EQUITY_L)
    code = main(["securities", "--symbol", "reliance", "--root", str(tmp_path)])
    assert code == 0
    assert "INE002A01018" in capsys.readouterr().out


def test_securities_missing_exits_one(tmp_path: Path) -> None:
    code = main(["securities", "--root", str(tmp_path)])
    assert code == 1


def test_equity_list_download(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.root = tmp_path

        def download(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=1, skipped_existing_count=0, failed_count=0)

    monkeypatch.setattr("powernse.cli.snapshots.EquityListDownloader", FakeDownloader)
    code = main(["equity-list", "--root", str(tmp_path)])
    assert code == 0


def test_bse_corporate_actions_download(tmp_path: Path, monkeypatch) -> None:
    class FakeDownloader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.root = tmp_path

        def download_range(self, *_args, **_kwargs) -> DownloadSummary:
            return DownloadSummary(downloaded_count=3, skipped_existing_count=0, failed_count=0)

    monkeypatch.setattr("powernse.cli.snapshots.BseCorporateActionsDownloader", FakeDownloader)
    code = main(["bse-corporate-actions", "--from", "2024-01-01", "--to", "2024-03-31", "--root", str(tmp_path)])
    assert code == 0


def test_index_history_help_exits_zero() -> None:
    assert main(["index-history", "--help"]) == 0


def test_index_history_runs_with_index_and_range(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeDownloader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.root = tmp_path

        def download_range(self, from_date, to_date, names) -> DownloadSummary:
            seen["args"] = (from_date, to_date, list(names))
            return DownloadSummary(downloaded_count=2, skipped_existing_count=0, failed_count=0)

    monkeypatch.setattr("powernse.cli.index_history.IndexHistoryDownloader", FakeDownloader)
    code = main(
        ["index-history", "--index", "NIFTY 50", "--from", "2001-01-01", "--to", "2001-01-03", "--root", str(tmp_path)]
    )
    assert code == 0
    assert seen["args"] == (date(2001, 1, 1), date(2001, 1, 3), ["NIFTY 50"])
