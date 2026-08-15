# Quickstart

Download official NSE India end-of-day archives, then query OHLC from the CLI or Python. When this project's GitHub repo publishes a populated `nse-data/` tree, you can also pull that tree as a zip.

## Install

```bash
pip install powernse
pip install 'powernse[pandas]'   # optional DataFrame helpers
```

From a clone:

```bash
uv sync
uv run powernse --help
```

## Download from NSE (always works)

```bash
powernse bhavcopy --resume
powernse fo-bhavcopy --resume --days 30
powernse index-closes --from 2024-08-01 --to 2024-08-05
powernse full-bhavcopy --from 2024-08-01 --to 2024-08-05
powernse bulk-deals --date 2024-08-09
powernse corporate-actions --from 2024-08-01 --to 2024-08-05
powernse doctor
powernse status
powernse ohlc RELIANCE --from 2024-08-01 --to 2024-08-05
```

`--resume` walks from the last staged day through today, capped by `--days` (default 100) when `--from` is omitted. For uncapped history: `powernse bhavcopy --resume --from 2000-01-01`.

Files land under `./nse-data/` (or `POWERNSE_ROOT` / `--root`).

## GitHub bundle (when the repo hosts data)

```bash
export POWERNSE_GITHUB_REPO=OWNER/REPO   # or set package [project.urls] Repository before publish
powernse fetch-bundle --force
powernse status
```

`--force` replaces the destination tree. Prefer a Release asset URL with `--url` when the code repo grows large; zipball of the whole repo remains the default.

Until `nse-data/` on GitHub contains CSV/JSON (not only placeholders), `fetch-bundle` will not give you bars — download from NSE first.

## Python

```python
from datetime import date
from powernse import BhavcopyDownloader, NSEData

BhavcopyDownloader("./nse-data").download_range(date(2024, 8, 1), date(2024, 8, 5))
data = NSEData("./nse-data")
bars = data.ohlc("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
```

OHLC helpers scan each day's CSV — prefer modest date windows.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success (zero download failures) |
| `1` | Download failures, doctor failure, empty query result, or domain error |
| `2` | Missing `--from`/`--to` when not using `--resume` |

## Next

- [Download archives](download/archives.md)
- [Use NSEData in Python](python/nsedata.md)
- [Fetch the GitHub nse-data bundle](bundle/fetch-bundle.md)
