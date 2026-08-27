"""Shared test builders. Public names -- imported by the test modules."""

import io
import zipfile
from datetime import date
from pathlib import Path

from powernse.archive import ArchiveRoot
from powernse.datasets import Dataset


def staged_path(root: Path, dataset: Dataset, day: date, *, discriminator: str = "") -> Path:
    """Where ``dataset``'s file for ``day`` lives under ``root`` (no I/O)."""
    return ArchiveRoot.connect(root).staged_path(dataset, day, discriminator=discriminator)


def staged_key(root: Path, dataset: Dataset, day: date, *, discriminator: str = "") -> str:
    return ArchiveRoot.connect(root).staged_key(dataset, day, discriminator=discriminator)


def write_staged(root: Path, dataset: Dataset, day: date, body: str, *, discriminator: str = "") -> Path:
    """Create a staged file for ``dataset``/``day`` with ``body`` and return its path."""
    path = staged_path(root, dataset, day, discriminator=discriminator)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def zip_bytes(*members: tuple[str, str]) -> bytes:
    """A ZIP archive of ``(name, text)`` members, as bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in members:
            archive.writestr(name, text)
    return buffer.getvalue()
