#!/usr/bin/env python
"""Regenerate ``src/powernse/resources/indexes.json`` from NSE's ``/api/allIndices``.

Maintainer tool -- hits live NSE, not run in CI or by users.

    uv run python scripts/build_index_catalog.py           # rewrite the catalog
    uv run python scripts/build_index_catalog.py --check    # exit 1 if it would change

Historical index-name aliases are NOT emitted here (the API only knows present-day
names) -- they live in ``src/powernse/index/aliases.py`` and are merged onto each
entry at ``IndexCatalog.load()``. This file stays alias-free so a regen never drops them.
"""

import argparse
import json
import sys
from pathlib import Path

from powernse.constants import ALL_INDICES_API_URL
from powernse.http import NseHttpClient

CATALOG = Path(__file__).resolve().parent.parent / "src" / "powernse" / "index" / "resources" / "indexes.json"

# NSE's `key` grouping -> our category. "INDICES ELIGIBLE IN DERIVATIVES" is an
# overlay of broad-market indexes, so it folds to "broad" + the fno flag.
CATEGORY = {
    "BROAD MARKET INDICES": "broad",
    "SECTORAL INDICES": "sectoral",
    "THEMATIC INDICES": "thematic",
    "STRATEGY INDICES": "strategy",
    "FIXED INCOME INDICES": "fixed_income",
    "INDICES ELIGIBLE IN DERIVATIVES": "broad",
}


def fetch_entries() -> list[dict[str, object]]:
    payload = NseHttpClient().fetch_bytes(ALL_INDICES_API_URL, accept="application/json")
    rows = json.loads(payload)["data"]
    entries = [
        {
            "name": row["index"].strip(),
            "code": row["indexSymbol"].strip(),
            "category": CATEGORY[row["key"]],
            "fno": row["key"] == "INDICES ELIGIBLE IN DERIVATIVES",
        }
        for row in rows
    ]
    entries.sort(key=lambda e: e["name"])
    return entries


def render(entries: list[dict[str, object]]) -> str:
    return json.dumps(entries, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the catalog is stale")
    args = parser.parse_args(argv)

    rendered = render(fetch_entries())
    current = CATALOG.read_text(encoding="utf-8") if CATALOG.is_file() else ""

    if args.check:
        if rendered == current:
            print(f"{CATALOG.name}: up to date")
            return 0
        print(f"{CATALOG.name}: STALE -- run scripts/build_index_catalog.py", file=sys.stderr)
        return 1

    CATALOG.write_text(rendered, encoding="utf-8")
    n = len(json.loads(rendered))
    print(f"{CATALOG.name}: wrote {n} indexes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
