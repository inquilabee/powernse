# PowerNSE

Download and use **official NSE India** equity archives from the command line or a few Python calls.

- CM **bhavcopy**, **F&O bhavcopy**, **full bhavcopy** (delivery), **index closes**
- **Bulk/block deals** and **F&O security ban** snapshots
- **Corporate actions** and **index constituent** snapshots
- Local archive layout with a download **manifest**
- **`fetch-bundle`** — pull the tracked `nse-data/` tree from GitHub as a zip
- XBOM trading-day calendar (weekdays before XBOM coverage; sessions after)

**Repo:** [github.com/inquilabee/powernse](https://github.com/inquilabee/powernse)

## Install

```bash
pip install powernse
pip install 'powernse[pandas]'   # optional DataFrame helpers
```

Requires Python 3.13+. Full install notes: [docs/user/install.md](docs/user/install.md).

## Quick start

Full guide: [docs/user/quickstart.md](docs/user/quickstart.md).

```bash
# Download from NSE
powernse bhavcopy --resume
powernse fo-bhavcopy --resume --days 30
powernse index-closes --from 2024-08-01 --to 2024-08-05
powernse full-bhavcopy --from 2024-08-01 --to 2024-08-05
powernse bulk-deals --date 2024-08-09

# Optional: GitHub-hosted nse-data (defaults to this repo after PyPI install)
powernse fetch-bundle --force

powernse status
powernse ohlc RELIANCE --from 2024-08-01 --to 2024-08-05
powernse doctor
```

```python
from datetime import date
from powernse import BhavcopyDownloader, NSEData

BhavcopyDownloader("./nse-data").download_range(date(2024, 8, 1), date(2024, 8, 5))
data = NSEData("./nse-data")
bars = data.ohlc("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
indexes = data.index_ohlc("Nifty 50")
```

## Docs

| Guide | Path |
| --- | --- |
| Install | [docs/user/install.md](docs/user/install.md) |
| Quickstart | [docs/user/quickstart.md](docs/user/quickstart.md) |
| Download archives | [docs/user/download/archives.md](docs/user/download/archives.md) |
| Python NSEData | [docs/user/python/nsedata.md](docs/user/python/nsedata.md) |
| GitHub bundle | [docs/user/bundle/fetch-bundle.md](docs/user/bundle/fetch-bundle.md) |
| Tracked archive notes | [nse-data/README.md](nse-data/README.md) |
| Publish to PyPI (maintainers) | [docs/maintainer/publish.md](docs/maintainer/publish.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## Archive layout

```text
nse-data/
  raw/bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/fo_bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/full_bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/index_closes/YYYY/YYYY-MM-DD.csv
  raw/bulk_deals/YYYY/YYYY-MM-DD.csv
  raw/block_deals/YYYY/YYYY-MM-DD.csv
  raw/fo_secban/YYYY/YYYY-MM-DD.csv
  raw/corporate_actions/YYYY/YYYY-MM-DD.json
  raw/index_constituents/YYYY/YYYY-MM-DD_<index>.json
  manifest/downloads.jsonl
```

## Be a good citizen

PowerNSE throttles requests and primes an NSE session cookie. Prefer modest date ranges; use `--skip-existing` (default) when resuming. NSE availability and URL shapes can change.

## Need a quick historical dump?

PowerNSE always prefers **official exchange archives**. If you only need rough historical OHLCV for experimentation, a public Kaggle dump such as [NSE India Stock Data (1990–2021)](https://www.kaggle.com/datasets/stoicstatic/india-stock-data-nse-1990-2020) may be good enough — download it yourself from Kaggle. This project does **not** fetch or ingest Kaggle datasets.

## Development

Quality gates use [ShipGate](https://inquilabee.github.io/shipgate/) (`suite: standard` in `.shipgate/shipgate.yaml`).

```bash
uv sync
make check      # shipgate install + check --full-tree
make format     # shipgate format
make test
make build
make install-hooks   # optional pre-commit
```

Release: [docs/maintainer/publish.md](docs/maintainer/publish.md) (tag `v*`).

## License

MIT — see [LICENSE](LICENSE).
