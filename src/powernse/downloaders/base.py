"""Shared archive downloader scaffold."""

import time
from collections.abc import Callable
from pathlib import Path

from powernse.archive import ArchiveRoot, record_download
from powernse.errors import DownloadError
from powernse.http import NseHttpClient, looks_like_html
from powernse.settings import Settings


class ArchiveDownloader:
    """Composable NSE archive fetch / throttle / persist scaffold."""

    def __init__(
        self,
        root: Path | str | ArchiveRoot | Settings,
        *,
        sleep_seconds: float | None = None,
        skip_existing: bool | None = None,
        fetch_bytes: Callable[[str], bytes] | None = None,
        default_accept: str = "*/*",
        http_client: NseHttpClient | None = None,
    ) -> None:
        settings, archive = self._resolve_root(root)
        self._archive = archive
        self._sleep_seconds = settings.sleep_seconds if sleep_seconds is None else sleep_seconds
        self._skip_existing = settings.skip_existing if skip_existing is None else skip_existing
        self._default_accept = default_accept
        if http_client is not None:
            self._http = http_client
        elif fetch_bytes is not None:
            self._http = NseHttpClient(fetch_override=fetch_bytes)
        else:
            self._http = NseHttpClient(min_interval_seconds=settings.min_request_interval_seconds)

    @staticmethod
    def _resolve_root(root: Path | str | ArchiveRoot | Settings) -> tuple[Settings, ArchiveRoot]:
        if isinstance(root, Settings):
            return root, ArchiveRoot.open(root.archive_root)
        if isinstance(root, ArchiveRoot):
            settings = Settings.resolve(root.root)
            return settings, root
        settings = Settings.resolve(root)
        return settings, ArchiveRoot.open(settings.archive_root)

    @property
    def archive(self) -> ArchiveRoot:
        return self._archive

    @property
    def root(self) -> Path:
        return self._archive.root

    @property
    def skip_existing(self) -> bool:
        return self._skip_existing

    def fetch_bytes_throttled(self, url: str) -> bytes:
        return self._http.fetch_bytes(url, accept=self._default_accept)

    def destination_exists(self, relative_key: str) -> bool:
        return self._archive.exists(relative_key)

    def persist_bytes(self, url: str, relative_key: str, payload: bytes, *, unavailable_message: str) -> Path:
        if looks_like_html(payload):
            raise DownloadError(unavailable_message)
        path = self._archive.write_bytes(relative_key, payload)
        record_download(self._archive, url=url, local_path=relative_key, payload=payload)
        if self._sleep_seconds > 0:
            time.sleep(self._sleep_seconds)
        return path

    def fetch_and_persist(self, url: str, relative_key: str, *, unavailable_message: str) -> Path:
        payload = self.fetch_bytes_throttled(url)
        return self.persist_bytes(url, relative_key, payload, unavailable_message=unavailable_message)
