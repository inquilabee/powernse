"""Sniff and unwrap downloaded payloads before they are staged.

NSE serves an HTML error page (HTTP 200) when a file is missing, and ships most
CSVs inside a single-member ZIP. Both checks live here so the HTTP client and the
downloaders share one implementation.
"""

import io
import zipfile
from pathlib import Path

from powernse.errors import PayloadError


def looks_like_html(payload: bytes, *, content_type: str | None = None) -> bool:
    """True when a payload is (or is served as) an HTML page rather than data."""
    if content_type is not None and "text/html" in content_type.lower():
        return True
    return payload[:512].lstrip().startswith(b"<")


def extract_csv_from_zip(payload: bytes, *, preferred_member: str | None = None) -> bytes:
    """Return the bytes of the single CSV member inside a ZIP payload.

    ``preferred_member`` disambiguates when several ``.csv`` members are present
    (by base name, case-insensitive); a lone member is always taken.
    """
    try:
        archive_cm = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        msg = "Response is not a ZIP archive"
        raise PayloadError(msg) from exc
    with archive_cm as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        chosen = pick_csv_member(members, preferred_member)
        with archive.open(chosen) as source:
            return source.read()


def pick_csv_member(members: list[str], preferred: str | None) -> str:
    if not members:
        msg = "No CSV member in archive"
        raise PayloadError(msg)
    if len(members) == 1:
        return members[0]
    if preferred is not None:
        matched = [name for name in members if Path(name).name.lower() == preferred.lower()]
        if len(matched) == 1:
            return matched[0]
    msg = f"Ambiguous CSV members in archive: {members}"
    raise PayloadError(msg)
