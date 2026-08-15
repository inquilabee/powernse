# Quickstart

Download official NSE India end-of-day archives, or pull a ready `nse-data/` tree from GitHub, then query OHLC from the CLI or Python.

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

## Fastest path: GitHub bundle

If this project hosts a tracked `nse-data/` directory on GitHub:

```bash
export POWERNSE_GITHUB_REPO=OWNER/REPO
powernse fetch-bundle --force
powernse status
powernse ohlc RELIANCE
```

`--force` overwrites a non-empty destination. Without env:

```bash
powernse fetch-bundle --repo OWNER/REPO --dest ./nse-data --force
```

## Download from NSE yourself

```bash
powernse bhavcopy --resume
powernse fo-bhavcopy --resume --days 30
powernse index-closes --from 2024-08-01 --to 2024-08-05
powernse full-bhavcopy --from 2024-08-01 --to 2024-08-05
powernse bulk-deals --date 2024-08-09
powernse corporate-actions --from 2024-08-01 --to 2024-08-05
powernse doctor
```

Files land under `./nse-data/` (or `POWERNSE_ROOT` / `--root`).

## Read OHLC

```bash
powernse ohlc RELIANCE --from 2024-08-01 --to 2024-08-05
powernse status
```

```python
from datetime import date
from powernse import BhavcopyDownloader, NSEData

BhavcopyDownloader("./nse-data").download_range(date(2024, 8, 1), date(2024, 8, 5))
data = NSEData("./nse-data")
bars = data.ohlc("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success (zero download failures) |
| `1` | Download failures, doctor failure, empty `ohlc`, or domain error |
| `2` | Missing `--from`/`--to` when not using `--resume` |

## Next

- [Download archives](download/archives.md)
- [Use NSEData in Python](python/nsedata.md)
- [Fetch the GitHub nse-data bundle](bundle/fetch-bundle.md)
