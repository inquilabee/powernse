"""Opt-in on-disk cache for expensive adjusted wide-frame reads.

``NSEData.wide_frame(adjusted=True)`` / ``wide_frames`` re-parse the whole staged
corporate-action archive on every call. This cache is content-addressed by the
request **plus the latest staged bhavcopy day**, so a refresh that stages a new
day misses the stale entry and it is recomputed. Any read error (a truncated
file, a pickle from another pandas) is treated as a miss: recompute + overwrite.
"""

import hashlib
import json
import os
import pickle
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Self

KeyParts = Mapping[str, object]


class WideFrameCache:
    """A parquet-free pickle cache for adjusted Date x Symbol matrices under a directory."""

    _SUBDIR = "wide_frame"

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir / self._SUBDIR

    @classmethod
    def resolve(cls, cache_dir: Path | str | None) -> Self | None:
        """A cache rooted at ``cache_dir``, or ``None`` when caching is not configured."""
        if cache_dir is None:
            return None
        return cls(Path(cache_dir).expanduser().resolve())

    def cached[T](self, parts: KeyParts, compute: Callable[[], T]) -> T:
        """Return the cached value for ``parts``; otherwise compute it, store it, return it."""
        path = self._path(parts)
        hit = self._load(path)
        if hit is not None:
            return hit
        value = compute()
        self._store(path, value)
        return value

    def _path(self, parts: KeyParts) -> Path:
        blob = json.dumps(dict(parts), sort_keys=True, default=str)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        return self._dir / f"{digest}.pkl"

    @staticmethod
    def _load(path: Path) -> object | None:
        try:
            with path.open("rb") as handle:
                return pickle.load(handle)
        except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ValueError, ImportError):
            return None

    @staticmethod
    def _store(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
