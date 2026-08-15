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
