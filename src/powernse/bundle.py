"""Download the tracked ``nse-data/`` tree from a GitHub repository zipball."""

import io
import logging
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path

import requests

from powernse.constants import BUNDLE_ARCHIVE_SUBDIR, DEFAULT_GITHUB_BRANCH, DEFAULT_USER_AGENT
from powernse.errors import DownloadError, PayloadError

logger = logging.getLogger(__name__)


class BundleFetcher:
    """Fetch a GitHub zipball (or Release zip URL) and extract the tracked ``nse-data`` tree."""

    def __init__(
        self,
        *,
        fetch_bytes: Callable[[str], bytes] | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._fetch_bytes = fetch_bytes
        self._timeout_seconds = timeout_seconds

    # -- source resolution -----------------------------------------------------

    @staticmethod
    def zipball_url(repo: str, branch: str = DEFAULT_GITHUB_BRANCH) -> str:
        """GitHub codeload zipball URL for ``owner/repo`` at ``branch``."""
        cleaned = repo.strip().strip("/")
        if cleaned.count("/") != 1:
            msg = f"GitHub repo must look like owner/name, got {repo!r}"
            raise ValueError(msg)
        return f"https://codeload.github.com/{cleaned}/zip/refs/heads/{branch}"

    @staticmethod
    def repo_from_package_metadata() -> str | None:
        """``owner/repo`` parsed from the installed package's Project-URL entries."""
        try:
            meta = metadata("powernse")
        except PackageNotFoundError:
            return None
        for item in meta.get_all("Project-URL") or ():
            label, _, value = item.partition(",")
            url = value.strip() or label.strip()
            if "github.com/" not in url:
                continue
            parts = [part for part in url.split("github.com/", 1)[1].strip("/").split("/") if part]
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
        return None

    # -- fetch + extract -----------------------------------------------------

    def fetch_url(self, url: str) -> bytes:
        if self._fetch_bytes is not None:
            return self._fetch_bytes(url)
        response = requests.get(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=self._timeout_seconds)
        if response.status_code >= 400:
            msg = f"Bundle download failed ({response.status_code}): {url}"
            raise DownloadError(msg)
        return response.content

    def download_to(
        self,
        dest: Path | str,
        *,
        repo: str | None = None,
        branch: str = DEFAULT_GITHUB_BRANCH,
        url: str | None = None,
        force: bool = False,
    ) -> int:
        """Download a zipball and extract ``nse-data`` into ``dest``. Returns the file count."""
        if url is None:
            resolved_repo = repo or self.repo_from_package_metadata()
            if not resolved_repo:
                msg = (
                    "Provide --repo owner/name, POWERNSE_GITHUB_REPO, --url "
                    "(Release asset or zipball), or set [project.urls] Repository on the package"
                )
                raise ValueError(msg)
            url = self.zipball_url(resolved_repo, branch)
        logger.info("Fetching bundle from %s", url)
        return self.extract(self.fetch_url(url), Path(dest), force=force)

    @classmethod
    def extract(cls, payload: bytes, dest: Path, *, subdir: str = BUNDLE_ARCHIVE_SUBDIR, force: bool = False) -> int:
        """Extract ``subdir/`` from a GitHub zipball into ``dest``. Returns files written."""
        dest = dest.expanduser().resolve()
        if dest.exists() and any(dest.iterdir()) and not force:
            msg = f"Destination {dest} is not empty; pass force=True to replace"
            raise FileExistsError(msg)

        with tempfile.TemporaryDirectory(prefix="powernse-bundle-") as tmp:
            staging = Path(tmp) / "nse-data"
            staging.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                prefix = cls._find_prefix(archive.namelist(), subdir=subdir)
                written = sum(cls._extract_member(archive, info, prefix, staging) for info in archive.infolist())
            if written == 0:
                msg = f"No files found under {subdir!r} in zipball"
                raise PayloadError(msg)
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(staging, dest)
        return written

    @staticmethod
    def _find_prefix(member_names: list[str], *, subdir: str) -> str:
        """The zip member prefix that ends at ``subdir/`` (trailing slash included)."""
        for name in member_names:
            parts = Path(name.replace("\\", "/")).parts
            if subdir in parts:
                return "/".join(parts[: parts.index(subdir) + 1]) + "/"
        msg = f"Zip archive has no {subdir!r} directory"
        raise PayloadError(msg)

    @staticmethod
    def _extract_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, prefix: str, staging: Path) -> int:
        """Write one in-scope member under ``staging``; return 1 if written, 0 if skipped."""
        name = info.filename.replace("\\", "/")
        if not name.startswith(prefix) or name.endswith("/"):
            return 0
        relative = name[len(prefix) :]
        if not relative or ".." in Path(relative).parts:
            return 0
        target = (staging / relative).resolve()
        if not target.is_relative_to(staging):
            msg = f"Zip member escapes destination: {name}"
            raise PayloadError(msg)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("wb") as handle:
            handle.write(source.read())
        return 1
