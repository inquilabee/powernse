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


def github_zipball_url(repo: str, branch: str = DEFAULT_GITHUB_BRANCH) -> str:
    """Return the GitHub codeload zipball URL for ``owner/repo`` at ``branch``."""
    cleaned = repo.strip().strip("/")
    if cleaned.count("/") != 1:
        msg = f"GitHub repo must look like owner/name, got {repo!r}"
        raise ValueError(msg)
    return f"https://codeload.github.com/{cleaned}/zip/refs/heads/{branch}"


def github_repo_from_package_metadata() -> str | None:
    """Parse ``owner/repo`` from installed package Project-URL homepage/repository entries."""
    try:
        meta = metadata("powernse")
    except PackageNotFoundError:
        return None
    for item in meta.get_all("Project-URL") or ():
        label, _, value = item.partition(",")
        url = value.strip() or label.strip()
        if "github.com/" not in url:
            continue
        tail = url.split("github.com/", 1)[1].strip("/")
        parts = [part for part in tail.split("/") if part]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return None


def find_nse_data_prefix(member_names: list[str], *, subdir: str = BUNDLE_ARCHIVE_SUBDIR) -> str:
    """Return the zip member prefix that ends at ``subdir/`` (including trailing slash)."""
    for name in member_names:
        normalized = name.replace("\\", "/")
        parts = Path(normalized).parts
        if subdir in parts:
            idx = parts.index(subdir)
            return "/".join(parts[: idx + 1]) + "/"
    msg = f"Zip archive has no {subdir!r} directory"
    raise PayloadError(msg)


def extract_nse_data_bundle(
    payload: bytes,
    dest: Path,
    *,
    subdir: str = BUNDLE_ARCHIVE_SUBDIR,
    force: bool = False,
) -> int:
    """Extract ``nse-data/`` from a GitHub zipball into ``dest``. Returns files written."""
    dest = dest.expanduser().resolve()
    if dest.exists() and any(dest.iterdir()) and not force:
        msg = f"Destination {dest} is not empty; pass force=True to replace"
        raise FileExistsError(msg)

    with tempfile.TemporaryDirectory(prefix="powernse-bundle-") as tmp:
        staging = Path(tmp) / "nse-data"
        staging.mkdir(parents=True, exist_ok=True)
        written = 0
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            prefix = find_nse_data_prefix(archive.namelist(), subdir=subdir)
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if not name.startswith(prefix) or name.endswith("/"):
                    continue
                relative = name[len(prefix) :]
                if not relative or ".." in Path(relative).parts:
                    continue
                target = (staging / relative).resolve()
                if not target.is_relative_to(staging):
                    msg = f"Zip member escapes destination: {name}"
                    raise PayloadError(msg)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as handle:
                    handle.write(source.read())
                written += 1
        if written == 0:
            msg = f"No files found under {subdir!r} in zipball"
            raise PayloadError(msg)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(staging, dest)
    return written


class BundleFetcher:
    """Fetch a GitHub zipball (or Release zip URL) and extract the tracked ``nse-data`` directory."""

    def __init__(
        self,
        *,
        fetch_bytes: Callable[[str], bytes] | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._fetch_bytes = fetch_bytes
        self._timeout_seconds = timeout_seconds

    def fetch_url(self, url: str) -> bytes:
        if self._fetch_bytes is not None:
            return self._fetch_bytes(url)
        response = requests.get(
            url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=self._timeout_seconds,
        )
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
        """Download zipball and extract ``nse-data`` into ``dest``. Returns file count."""
        if url is None:
            resolved_repo = repo or github_repo_from_package_metadata()
            if not resolved_repo:
                msg = (
                    "Provide --repo owner/name, POWERNSE_GITHUB_REPO, --url "
                    "(Release asset or zipball), or set [project.urls] Repository on the package"
                )
                raise ValueError(msg)
            url = github_zipball_url(resolved_repo, branch)
        logger.info("Fetching bundle from %s", url)
        payload = self.fetch_url(url)
        return extract_nse_data_bundle(payload, Path(dest), force=force)
