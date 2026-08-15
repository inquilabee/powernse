"""Tests for GitHub nse-data bundle fetch."""

import io
import zipfile
from pathlib import Path

import pytest

from powernse.bundle import BundleFetcher, extract_nse_data_bundle, github_zipball_url
from powernse.errors import PayloadError


def _repo_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_github_zipball_url() -> None:
    assert github_zipball_url("acme/powernse", "main") == (
        "https://codeload.github.com/acme/powernse/zip/refs/heads/main"
    )


def test_extract_nse_data_bundle(tmp_path: Path) -> None:
    payload = _repo_zip(
        {
            "acme-powernse-abc/nse-data/raw/bhavcopy/2024/2024-08-01.csv": "SYMBOL\nRELIANCE\n",
            "acme-powernse-abc/nse-data/README.md": "# data\n",
            "acme-powernse-abc/README.md": "skip\n",
        }
    )
    dest = tmp_path / "out"
    written = extract_nse_data_bundle(payload, dest)
    assert written == 2
    assert (dest / "raw" / "bhavcopy" / "2024" / "2024-08-01.csv").read_text(encoding="utf-8").startswith("SYMBOL")
    assert (dest / "README.md").is_file()


def test_extract_rejects_missing_subdir(tmp_path: Path) -> None:
    payload = _repo_zip({"acme-powernse-abc/README.md": "x\n"})
    with pytest.raises(PayloadError, match="nse-data"):
        extract_nse_data_bundle(payload, tmp_path / "out")


def test_bundle_fetcher_uses_repo_url(tmp_path: Path) -> None:
    payload = _repo_zip({"owner-repo-sha/nse-data/raw/x.csv": "a,b\n"})

    def fetch(url: str) -> bytes:
        assert "codeload.github.com/owner/repo/zip/refs/heads/main" in url
        return payload

    written = BundleFetcher(fetch_bytes=fetch).download_to(tmp_path / "nse", repo="owner/repo", force=True)
    assert written == 1


def test_force_replaces_orphan_files(tmp_path: Path) -> None:
    dest = tmp_path / "nse"
    dest.mkdir()
    orphan = dest / "raw" / "old.csv"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("orphan\n", encoding="utf-8")
    payload = _repo_zip({"owner-repo-sha/nse-data/raw/new.csv": "ok\n"})
    written = extract_nse_data_bundle(payload, dest, force=True)
    assert written == 1
    assert (dest / "raw" / "new.csv").is_file()
    assert not orphan.exists()


def test_fetch_bundle_cli_missing_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from powernse.cli import main

    monkeypatch.delenv("POWERNSE_GITHUB_REPO", raising=False)
    monkeypatch.setattr("powernse.cli.bundle_cmd.github_repo_from_package_metadata", lambda: None)
    monkeypatch.setattr("powernse.bundle.github_repo_from_package_metadata", lambda: None)
    code = main(["fetch-bundle", "--dest", str(tmp_path / "empty")])
    assert code == 1


def test_github_repo_from_package_metadata_reads_urls() -> None:
    from powernse.bundle import github_repo_from_package_metadata

    assert github_repo_from_package_metadata() == "inquilabee/powernse"
