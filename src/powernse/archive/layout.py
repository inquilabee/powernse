"""Filesystem archive layout for staged NSE downloads."""

import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Self

from powernse.datasets import ALL as ALL_DATASETS
from powernse.datasets import Dataset

MANIFEST_DIR = Path("manifest")

BOOTSTRAP_DIRS = (*(dataset.raw_dir for dataset in ALL_DATASETS), MANIFEST_DIR)

IGNORED_PLACEHOLDER_NAMES = frozenset({".keep", ".gitkeep"})


@dataclass(slots=True)
class ArchiveRoot:
    """Lifecycle owner for a local NSE archive tree."""

    root: Path

    @classmethod
    def open(cls, root: Path | str) -> Self:
        """Open an archive root, creating the standard layout directories."""
        resolved = Path(root).expanduser().resolve()
        return cls(root=resolved)._bootstrap()

    @classmethod
    def connect(cls, root: Path | str) -> Self:
        """Attach to an archive root without creating directories."""
        resolved = Path(root).expanduser().resolve()
        return cls(root=resolved)

    def _bootstrap(self) -> Self:
        for relative in BOOTSTRAP_DIRS:
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        return self

    def path_for(self, *parts: str | Path) -> Path:
        target = self.root.joinpath(*[Path(part) for part in parts])
        resolved = target.resolve()
        if not resolved.is_relative_to(self.root):
            msg = f"path escapes archive root: {target}"
            raise ValueError(msg)
        return resolved

    def relative_key(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def exists(self, relative: str | Path) -> bool:
        return self.path_for(relative).is_file()

    # -- Dataset-addressed staging -------------------------------------------------

    def staged_path(self, dataset: Dataset, day: date, *, discriminator: str = "") -> Path:
        """Absolute path where ``dataset``'s file for ``day`` is (or would be) staged."""
        return self.path_for(dataset.relpath(day, discriminator=discriminator))

    def staged_key(self, dataset: Dataset, day: date, *, discriminator: str = "") -> str:
        """Archive-relative POSIX key for ``dataset``'s file for ``day``."""
        return dataset.relpath(day, discriminator=discriminator).as_posix()

    def has_staged(self, dataset: Dataset, day: date, *, discriminator: str = "") -> bool:
        return self.staged_path(dataset, day, discriminator=discriminator).is_file()

    def staged_dates(self, dataset: Dataset) -> list[date]:
        """Every staged day for ``dataset``, ascending and de-duplicated."""
        seen = {day for path in self.list_files(dataset.raw_dir) if (day := dataset.date_of(path)) is not None}
        return sorted(seen)

    def latest_staged_date(self, dataset: Dataset) -> date | None:
        dates = self.staged_dates(dataset)
        return dates[-1] if dates else None

    # -- Bytes ------------------------------------------------------------------

    def write_bytes(self, relative: str | Path, payload: bytes) -> Path:
        path = self.path_for(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return path

    def read_bytes(self, relative: str | Path) -> bytes:
        path = self.path_for(relative)
        if not path.is_file():
            msg = f"object not found: {relative}"
            raise FileNotFoundError(msg)
        return path.read_bytes()

    def list_files(self, relative_prefix: str | Path = "") -> list[Path]:
        search = self.path_for(relative_prefix) if relative_prefix else self.root
        if not search.exists():
            return []
        if search.is_file():
            return [search]
        return sorted(
            path for path in search.rglob("*") if path.is_file() and path.name not in IGNORED_PLACEHOLDER_NAMES
        )
