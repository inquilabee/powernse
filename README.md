# PowerNSE

Download and use **official NSE India** equity archives from the command line or a few Python calls.

- CM **bhavcopy** (legacy + UDIFF ZIP formats)
- **Corporate actions** JSON
- **Index constituent** snapshots
- Local archive layout with a download **manifest**
- XBOM trading-day calendar (skips weekends/holidays by default)

## Install

```bash
pip install powernse
pip install 'powernse[pandas]'   # optional DataFrame helpers
```

Requires Python 3.13+.

## Quick start (CLI)

```bash
# Archive root defaults to ./nse-data (override with --root or POWERNSE_ROOT)
powernse bhavcopy --from 2024-08-01 --to 2024-08-05
powernse corporate-actions --from 2024-08-01 --to 2024-08-05
powernse index-constituents --index "NIFTY 50"
powernse status
powernse doctor
```

See [docs/user/quickstart.md](docs/user/quickstart.md).

## Quick start (Python)

```python
from datetime import date
from powernse import BhavcopyDownloader, ArchiveReader

BhavcopyDownloader("./nse-data").download_range(date(2024, 8, 1), date(2024, 8, 5))
rows = ArchiveReader("./nse-data").bhavcopy_rows(date(2024, 8, 1))
```

## Archive layout

```text
nse-data/
  raw/bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/corporate_actions/YYYY/YYYY-MM-DD.json
  raw/index_constituents/YYYY/YYYY-MM-DD_<index>.json
  manifest/downloads.jsonl
```

## Be a good citizen

PowerNSE throttles requests and primes an NSE session cookie. Prefer modest date ranges; use `--skip-existing` (default) when resuming. NSE availability and URL shapes can change.

## Need a quick historical dump?

PowerNSE always prefers **official exchange archives**. If you only need rough historical OHLCV for experimentation, a public Kaggle dump such as [NSE India Stock Data (1990–2021)](https://www.kaggle.com/datasets/stoicstatic/india-stock-data-nse-1990-2020) may be good enough — download it yourself from Kaggle. This project does **not** fetch or ingest Kaggle datasets.

## Development

```bash
uv sync
make check
make test
make build
```

## License

MIT — see [LICENSE](LICENSE).
