"""Runtime settings resolved from env and explicit overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from powernse.constants import (
    DEFAULT_ARCHIVE_DIRNAME,
    DEFAULT_SLEEP_SECONDS,
    ENV_ARCHIVE_ROOT,
    MIN_REQUEST_INTERVAL_SECONDS,
)


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved runtime configuration for downloads."""

    archive_root: Path
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS
    min_request_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS
    skip_existing: bool = True
    strict: bool = False

    @classmethod
    def resolve(
        cls,
        root: Path | str | None = None,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
    ) -> Settings:
        archive_root = cls._resolve_root(root)
        return cls(
            archive_root=archive_root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            strict=strict,
        )

    @staticmethod
    def _resolve_root(root: Path | str | None) -> Path:
        if root is not None:
            return Path(root).expanduser().resolve()
        env = os.environ.get(ENV_ARCHIVE_ROOT)
        if env:
            return Path(env).expanduser().resolve()
        return (Path.cwd() / DEFAULT_ARCHIVE_DIRNAME).resolve()
