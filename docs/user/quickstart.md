# Quickstart

Download NSE India end-of-day archives, then query OHLC from the CLI or Python. You can also pull this project's tracked `nse-data/` tree from GitHub as a zip when it contains archives.

!!! warning "Disclaimer"

    PowerNSE is **not affiliated with NSE**. Use for **educational and research**
    purposes only. The author bears **no responsibility** for anything that goes
    wrong — trading losses, blocked access, bad data, or otherwise. See
    [Disclaimer](disclaimer.md).

## Install

See [Install](install.md).

```bash
pip install powernse
powernse --help
```

From a clone: `uv sync` then `uv run powernse --help`.

## Download from NSE (always works)

```bash
powernse bhavcopy --resume
powernse fo-bhavcopy --resume --days 30
powernse index-closes --from 2024-08-01 --to 2024-08-05
powernse full-bhavcopy --from 2024-08-01 --to 2024-08-05
powernse bulk-deals --date 2024-08-09
powernse equity-list --date 2024-08-09
powernse corporate-actions --from 2024-08-01 --to 2024-08-05
powernse doctor
powernse status
powernse verify --hashes              # session gaps + manifest sha256 audit (exit 1 if any)
powernse securities --symbol RELIANCE
powernse ohlc RELIANCE --from 2024-08-01 --to 2024-08-05
```

`--resume` walks from the last staged day through today, capped by `--days` (default 100) when `--from` is omitted. For uncapped history: `powernse bhavcopy --resume --from 2000-01-01`.

Dates before **2006-08-16** walk Monday–Friday (XBOM holiday data in `exchange-calendars` starts then). Missing NSE archives still count as download failures.

Files land under `./nse-data/` (or `POWERNSE_ROOT` / `--root`).

## GitHub bundle

After `pip install powernse`, no env var is required (the wheel embeds the Repository URL):

```bash
powernse fetch-bundle --force
powernse status
```

Or pin the repo explicitly:

```bash
powernse fetch-bundle --repo inquilabee/powernse --force
# export POWERNSE_GITHUB_REPO=inquilabee/powernse
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
adj = data.ohlc_adjusted("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
```

OHLC helpers scan each day's CSV — prefer modest date windows. Full API:
[Use NSEData in Python](python/nsedata.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success (zero download failures) |
| `1` | Download failures, doctor failure, empty query result, or domain error |
| `2` | Missing `--from`/`--to` when not using `--resume` |

## Next

- [Install](install.md)
- [Download archives](download/archives.md)
- [Use NSEData in Python](python/nsedata.md)
- [Fetch the GitHub nse-data bundle](bundle/fetch-bundle.md)
- [Disclaimer](disclaimer.md)
