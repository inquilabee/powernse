"""Archive layout containment and status side effects."""

from pathlib import Path

import pytest

from powernse.archive import ArchiveRoot
from powernse.cli import main


def test_path_for_rejects_prefix_collision_escape(tmp_path: Path) -> None:
    archive = ArchiveRoot.open(tmp_path / "archive")
    evil = tmp_path / "archive-evil"
    with pytest.raises(ValueError, match="escapes"):
        archive.write_bytes(Path("..") / "archive-evil" / "pwned.txt", b"nope")
    assert not evil.exists()


def test_path_for_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = ArchiveRoot.open(tmp_path / "archive")
    with pytest.raises(ValueError, match="escapes"):
        archive.path_for("..", "outside.txt")


def test_write_bytes_is_atomic(tmp_path: Path) -> None:
    archive = ArchiveRoot.open(tmp_path)
    path = archive.write_bytes("raw/bhavcopy/2024/x.csv", b"hello")
    assert path.read_bytes() == b"hello"
    leftovers = list(path.parent.glob(".x.csv.*"))
    assert leftovers == []


def test_status_does_not_create_layout(tmp_path: Path) -> None:
    empty = tmp_path / "empty-root"
    empty.mkdir()
    code = main(["status", "--root", str(empty)])
    assert code == 0
    assert not (empty / "raw").exists()
    assert not (empty / "manifest").exists()
