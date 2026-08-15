"""Filesystem archive layout for staged NSE downloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

RAW_BHAVCOPY_DIR = Path("raw") / "bhavcopy"
RAW_CORPORATE_ACTIONS_DIR = Path("raw") / "corporate_actions"
RAW_INDEX_CONSTITUENTS_DIR = Path("raw") / "index_constituents"
MANIFEST_DIR = Path("manifest")

ARCHIVE_PREFIX_DIRS = (
    RAW_BHAVCOPY_DIR,
    RAW_CORPORATE_ACTIONS_DIR,
    RAW_INDEX_CONSTITUENTS_DIR,
    MANIFEST_DIR,
)


def archive_key(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part)


@dataclass(slots=True)
class ArchiveRoot:
    """Lifecycle owner for a local NSE archive tree."""

    root: Path

    @classmethod
    def open(cls, root: Path | str) -> ArchiveRoot:
        resolved = Path(root).expanduser().resolve()
        return cls(root=resolved)._bootstrap()

    def _bootstrap(self) -> ArchiveRoot:
        for relative in ARCHIVE_PREFIX_DIRS:
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        return self

    def path_for(self, *parts: str | Path) -> Path:
        target = self.root.joinpath(*[Path(part) for part in parts])
        resolved = target.resolve()
        if not str(resolved).startswith(str(self.root)):
            msg = f"path escapes archive root: {target}"
            raise ValueError(msg)
        return resolved

    def relative_key(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def exists(self, relative: str | Path) -> bool:
        return self.path_for(relative).is_file()

    def write_bytes(self, relative: str | Path, payload: bytes) -> Path:
        path = self.path_for(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
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
        return sorted(path for path in search.rglob("*") if path.is_file() and path.name != ".keep")
