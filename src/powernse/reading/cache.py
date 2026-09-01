"""Opt-in on-disk cache for expensive adjusted wide-frame reads.

``NSEData.wide_frame(adjusted=True)`` / ``wide_frames`` re-parse the whole staged
corporate-action archive on every call. This cache is content-addressed by the
request **plus the latest staged bhavcopy day**, so a refresh that stages a new
day misses the stale entry and it is recomputed. Any read error (a truncated
file, a frame written by another pandas) is treated as a miss: recompute +
overwrite.

Storage is one Parquet file per Date x Symbol matrix (``pyarrow``); the index is
normalised to a ``DatetimeIndex`` on write and back to ``datetime.date`` on read
so a cached frame equals a freshly computed one.
"""

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Self

import pandas as pd
import pyarrow

KeyParts = Mapping[str, object]


class WideFrameCache:
    """A Parquet cache for adjusted Date x Symbol matrices under a directory."""

    _SUBDIR = "wide_frame"

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir / self._SUBDIR

    @classmethod
    def resolve(cls, cache_dir: Path | str | None) -> Self | None:
        """A cache rooted at ``cache_dir``, or ``None`` when caching is not configured."""
        if cache_dir is None:
            return None
        return cls(Path(cache_dir).expanduser().resolve())

    def frame(self, parts: KeyParts, compute: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        """The cached matrix for ``parts``; otherwise compute it, store it, return it."""
        hit = self.get(parts)
        if hit is not None:
            return hit
        fresh = compute()
        self.put(parts, fresh)
        return fresh

    def frames(
        self,
        columns: tuple[str, ...],
        *,
        key_for: Callable[[str], KeyParts],
        compute: Callable[[list[str]], dict[str, pd.DataFrame]],
    ) -> dict[str, pd.DataFrame]:
        """Per-column cache lookup: serve the hits, compute only the misses in one pass, store them."""
        keys = {col: key_for(col) for col in columns}
        found: dict[str, pd.DataFrame] = {}
        missing: list[str] = []
        for col, parts in keys.items():
            hit = self.get(parts)
            if hit is None:
                missing.append(col)
            else:
                found[col] = hit
        for col, frame in compute(missing).items():
            self.put(keys[col], frame)
            found[col] = frame
        return {col: found[col] for col in columns if col in found}

    def get(self, parts: KeyParts) -> pd.DataFrame | None:
        path = self._path(parts)
        try:
            stored = pd.read_parquet(path)
        except (OSError, ValueError, pyarrow.ArrowInvalid):
            return None
        stored.index = [ts.date() for ts in pd.to_datetime(stored.index)]  # -> object index of datetime.date
        stored.index.name = "Date"
        return stored

    def put(self, parts: KeyParts, frame: pd.DataFrame) -> None:
        if frame.empty:  # nothing worth a file; recompute is already trivial
            return
        path = self._path(parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        out = frame.copy()
        out.index = pd.to_datetime(out.index)
        out.index.name = "Date"
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            out.to_parquet(tmp_path)
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _path(self, parts: KeyParts) -> Path:
        blob = json.dumps(dict(parts), sort_keys=True, default=str)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        return self._dir / f"{digest}.parquet"
