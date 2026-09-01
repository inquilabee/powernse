"""Runtime settings resolved from env and explicit overrides."""

from pathlib import Path
from typing import Self

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from powernse.constants import (
    DEFAULT_ARCHIVE_DIRNAME,
    DEFAULT_GITHUB_BRANCH,
    DEFAULT_SLEEP_SECONDS,
    ENV_ARCHIVE_ROOT,
    ENV_CACHE_DIR,
    ENV_GITHUB_BRANCH,
    ENV_GITHUB_REPO,
    MIN_REQUEST_INTERVAL_SECONDS,
)


class EnvSettings(BaseSettings):
    """Process environment settings for PowerNSE."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    powernse_root: Path | None = Field(default=None, validation_alias=ENV_ARCHIVE_ROOT)
    powernse_cache_dir: Path | None = Field(default=None, validation_alias=ENV_CACHE_DIR)
    powernse_github_repo: str | None = Field(default=None, validation_alias=ENV_GITHUB_REPO)
    powernse_github_branch: str = Field(default=DEFAULT_GITHUB_BRANCH, validation_alias=ENV_GITHUB_BRANCH)


class Settings:
    """Resolved runtime configuration for downloads."""

    __slots__ = (
        "archive_root",
        "github_branch",
        "github_repo",
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
        github_repo: str | None = None,
        github_branch: str = DEFAULT_GITHUB_BRANCH,
    ) -> None:
        self.archive_root = archive_root
        self.sleep_seconds = sleep_seconds
        self.min_request_interval_seconds = min_request_interval_seconds
        self.skip_existing = skip_existing
        self.strict = strict
        self.github_repo = github_repo
        self.github_branch = github_branch

    @classmethod
    def resolve(
        cls,
        root: Path | str | None = None,
        *,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        skip_existing: bool = True,
        strict: bool = False,
    ) -> Self:
        env = EnvSettings()
        archive_root = cls._resolve_root(root, env)
        return cls(
            archive_root=archive_root,
            sleep_seconds=sleep_seconds,
            skip_existing=skip_existing,
            strict=strict,
            github_repo=env.powernse_github_repo,
            github_branch=env.powernse_github_branch or DEFAULT_GITHUB_BRANCH,
        )

    @staticmethod
    def _resolve_root(root: Path | str | None, env: EnvSettings | None = None) -> Path:
        if root is not None:
            return Path(root).expanduser().resolve()
        resolved_env = env or EnvSettings()
        if resolved_env.powernse_root is not None:
            return resolved_env.powernse_root.expanduser().resolve()
        return (Path.cwd() / DEFAULT_ARCHIVE_DIRNAME).resolve()
