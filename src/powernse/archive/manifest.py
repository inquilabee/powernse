"""Download audit manifest (JSONL)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from powernse.archive.layout import MANIFEST_DIR, ArchiveRoot


@dataclass(frozen=True, slots=True)
class DownloadManifestEntry:
    """Single raw download audit record."""

    url: str
    sha256: str
    fetched_at: str
    local_path: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "url": self.url,
                "sha256": self.sha256,
                "fetched_at": self.fetched_at,
                "local_path": self.local_path,
            }
        )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_000_000), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(archive: ArchiveRoot) -> Path:
    return archive.path_for(MANIFEST_DIR, "downloads.jsonl")


def append_manifest_entry(archive: ArchiveRoot, entry: DownloadManifestEntry) -> None:
    path = manifest_path(archive)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry.to_json() + "\n")


def record_download(archive: ArchiveRoot, *, url: str, local_path: str, payload: bytes) -> None:
    append_manifest_entry(
        archive,
        DownloadManifestEntry(
            url=url,
            sha256=sha256_bytes(payload),
            fetched_at=datetime.now(UTC).isoformat(),
            local_path=local_path,
        ),
    )
