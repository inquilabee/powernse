"""Check staged files against the sha256 recorded per download in the manifest."""

import json
from dataclasses import dataclass
from typing import Literal

from powernse.archive import manifest_path, sha256_file
from powernse.reading.base import ArchiveReader

IssueKind = Literal["missing", "sha256"]


@dataclass(frozen=True, slots=True)
class ManifestIssue:
    """One staged file that no longer matches its manifest record."""

    local_path: str
    kind: IssueKind


class ManifestAudit(ArchiveReader):
    """Re-hash every file named in ``manifest/downloads.jsonl`` and report drift."""

    def issues(self) -> list[ManifestIssue]:
        """Manifest-listed files that are missing on disk or whose sha256 no longer matches."""
        path = manifest_path(self._archive)
        if not path.is_file():
            return []
        recorded: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            recorded[entry["local_path"]] = entry["sha256"]  # keep the newest record per path
        return [issue for local_path, digest in recorded.items() if (issue := self._check(local_path, digest))]

    def _check(self, local_path: str, digest: str) -> ManifestIssue | None:
        target = self._archive.path_for(local_path)
        if not target.is_file():
            return ManifestIssue(local_path, "missing")
        if sha256_file(target) != digest:
            return ManifestIssue(local_path, "sha256")
        return None
