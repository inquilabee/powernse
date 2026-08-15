# Quickstart

## Install

```bash
pip install powernse
# optional DataFrame helpers
pip install 'powernse[pandas]'
```

From a clone:

```bash
uv sync
uv run powernse --help
```

## Download bhavcopy

```bash
powernse bhavcopy --from 2024-08-01 --to 2024-08-05
```

Files land under `./nse-data/raw/bhavcopy/YYYY/YYYY-MM-DD.csv` (or `POWERNSE_ROOT`).

Default date walking uses the XBOM trading calendar. Pass `--all-calendar-days` only when you intentionally want weekends and holidays included.

## Corporate actions and indices

```bash
powernse corporate-actions --from 2024-08-01 --to 2024-08-05
powernse index-constituents --index "NIFTY 50" --label-date 2024-08-05
```

Index constituent downloads are **live as-of download time**. `--label-date` only names the staged file; it does not request a historical membership list.

## Check the archive

```bash
powernse status
powernse doctor
```

`status` never creates archive directories. Download commands create the layout on first write.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Command completed with zero failures |
| `1` | Validation / download / connectivity failure (`failed_count > 0`, doctor failure, or domain error) |

`--strict` aborts a range on the first hard failure instead of counting and continuing.

## Python

```python
from datetime import date
from powernse import BhavcopyDownloader, ArchiveReader

root = "./nse-data"
BhavcopyDownloader(root).download_range(date(2024, 8, 1), date(2024, 8, 5))

reader = ArchiveReader(root)
rows = reader.bhavcopy_rows(date(2024, 8, 1))
# with pandas extra:
# frame = reader.bhavcopy_frame(date(2024, 8, 1))
```
