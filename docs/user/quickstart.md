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

## Corporate actions and indices

```bash
powernse corporate-actions --from 2024-08-01 --to 2024-08-05
powernse index-constituents --index "NIFTY 50" --date 2024-08-05
```

## Check the archive

```bash
powernse status
powernse doctor
```

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
