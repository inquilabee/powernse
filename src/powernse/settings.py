"""Runtime settings resolved from env and explicit overrides."""

from pathlib import Path
from typing import Self

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from powernse.constants import (
    DEFAULT_ARCHIVE_DIRNAME,
    DEFAULT_SLEEP_SECONDS,
    ENV_ARCHIVE_ROOT,
    MIN_REQUEST_INTERVAL_SECONDS,
)


class EnvSettings(BaseSettings):
    """Process environment settings for PowerNSE."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    powernse_root: Path | None = Field(default=None, validation_alias=ENV_ARCHIVE_ROOT)


class Settings:
    """Resolved runtime configuration for downloads."""

    __slots__ = (
        "archive_root",
        "min_request_interval_seconds",
        "skip_existing",
        "sleep_seconds",
        "strict",
    )

    def __init__(
        self,
        archive_root: Path,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        min_request_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
    ) -> None:
        self.archive_root = archive_root
        self.sleep_seconds = sleep_seconds
        self.min_request_interval_seconds = min_request_interval_seconds
        self.skip_existing = skip_existing
        self.strict = strict

    @classmethod
    def resolve(
        cls,
        root: Path | str | None = None,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
    ) -> Self:
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
        env = EnvSettings()
        if env.powernse_root is not None:
            return env.powernse_root.expanduser().resolve()
        return (Path.cwd() / DEFAULT_ARCHIVE_DIRNAME).resolve()
