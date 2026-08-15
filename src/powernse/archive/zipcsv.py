"""Extract a single CSV member from a ZIP payload."""

import io
import zipfile
from pathlib import Path

from powernse.errors import PayloadError


def extract_zip_payload_to_csv_bytes(payload: bytes, *, preferred_member: str | None = None) -> bytes:
    """Return bytes of the chosen CSV member inside a ZIP archive."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not members:
            msg = "No CSV member in archive"
            raise PayloadError(msg)
        if preferred_member is not None:
            matched = [name for name in members if Path(name).name.lower() == preferred_member.lower()]
            if len(matched) == 1:
                chosen = matched[0]
            elif len(members) == 1:
                chosen = members[0]
            else:
                msg = f"Ambiguous CSV members in archive: {members}"
                raise PayloadError(msg)
        elif len(members) == 1:
            chosen = members[0]
        else:
            msg = f"Ambiguous CSV members in archive: {members}"
            raise PayloadError(msg)
        with archive.open(chosen) as source:
            return source.read()
