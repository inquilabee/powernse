"""Manifest sha256 audit (powernse verify --hashes)."""

from pathlib import Path

from powernse import NSEData
from powernse.archive import ArchiveRoot, record_download


def _staged(archive: ArchiveRoot, key: str, payload: bytes) -> None:
    archive.write_bytes(key, payload)
    record_download(archive, url=f"https://example.test/{key}", local_path=key, payload=payload)


def test_audit_manifest_flags_tamper_and_missing(tmp_path: Path) -> None:
    archive = ArchiveRoot.open(tmp_path)
    _staged(archive, "raw/bhavcopy/2024/2024-08-01.csv", b"clean,row\n1,2\n")
    _staged(archive, "raw/bhavcopy/2024/2024-08-02.csv", b"another,row\n3,4\n")
    _staged(archive, "raw/index_closes/2024/2024-08-01.csv", b"idx,close\nNIFTY,1\n")

    data = NSEData(tmp_path)
    assert data.audit_manifest() == []  # nothing touched yet

    # tamper with one file, delete another
    (tmp_path / "raw/bhavcopy/2024/2024-08-01.csv").write_bytes(b"tampered\n")
    (tmp_path / "raw/index_closes/2024/2024-08-01.csv").unlink()

    issues = {(i.local_path, i.kind) for i in data.audit_manifest()}
    assert issues == {
        ("raw/bhavcopy/2024/2024-08-01.csv", "sha256"),
        ("raw/index_closes/2024/2024-08-01.csv", "missing"),
    }


def test_audit_manifest_empty_without_manifest(tmp_path: Path) -> None:
    assert NSEData(tmp_path).audit_manifest() == []


def test_verify_hashes_cli_exit(tmp_path: Path) -> None:
    from powernse.cli import main

    archive = ArchiveRoot.open(tmp_path)
    _staged(archive, "raw/bhavcopy/2024/2024-08-01.csv", b"clean\n")
    day = ["--dataset", "bhavcopy", "--from", "2024-08-01", "--to", "2024-08-01", "--root", str(tmp_path)]

    assert main(["verify", "--hashes", *day]) == 0  # no gap in the window, hash matches

    (tmp_path / "raw/bhavcopy/2024/2024-08-01.csv").write_bytes(b"tampered\n")
    assert main(["verify", "--hashes", *day]) == 1  # hash drift trips the exit
    assert main(["verify", *day]) == 0  # ...but only with --hashes
