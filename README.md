<p align="center">
  <a href="https://pypi.org/project/powernse/"><img src="https://img.shields.io/pypi/v/powernse.svg" alt="PyPI version"/></a>
  <a href="https://pypi.org/project/powernse/"><img src="https://img.shields.io/pypi/pyversions/powernse.svg" alt="Python versions"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"/></a>
  <a href="https://inquilabee.github.io/powernse/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue" alt="Documentation"/></a>
</p>

<p align="center">
  <strong>Official NSE India archives on disk. One CLI. A small Python API.</strong><br/>
  Bhavcopy, F&amp;O, indexes, deals, corporate actions — downloaded from the exchange,
  not scraped from a third-party dump.
</p>

<p align="center">
  <a href="https://inquilabee.github.io/powernse/">Docs</a> ·
  <a href="https://inquilabee.github.io/powernse/user/quickstart/">Quick start</a> ·
  <a href="https://pypi.org/project/powernse/">PyPI</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

______________________________________________________________________

NSE publishes end-of-day files. The URLs move, the session cookie is picky, and
nobody wants to re-learn the layout every quarter. **PowerNSE** stages those
archives under a local `nse-data/` tree, keeps a download manifest, and lets you
query OHLC from the CLI or from Python.

Need a ready-made tree? `powernse fetch-bundle` pulls the tracked `nse-data/` from
this GitHub repo. Prefer building it yourself? Point the downloaders at NSE.

Python **3.13+**.

## Install

```bash
pip install powernse
pip install 'powernse[pandas]'   # optional DataFrame helpers
```

## Quick start

```bash
powernse bhavcopy --resume
powernse fo-bhavcopy --resume --days 30
powernse index-closes --from 2024-08-01 --to 2024-08-05
powernse fetch-bundle --force    # optional: GitHub-hosted archive
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
```

Full walkthrough: [docs site quickstart](https://inquilabee.github.io/powernse/user/quickstart/).

## What you get

| Surface | Covers |
| --- | --- |
| Cash / F&O / full bhavcopy | Daily equity and derivatives archives |
| Index closes & constituents | Index levels and membership snapshots |
| Bulk / block deals, F&O ban | As-of snapshots |
| Corporate actions | JSON for adjustment helpers |
| `NSEData` / CLI | OHLC, coverage gaps, inventory, doctor |
| `fetch-bundle` | Zip extract of this repo's `nse-data/` |

Trading days use XBOM sessions when `exchange-calendars` covers the window
(from 2006-08-16). Earlier dates fall back to weekdays.

## Archive layout

```text
nse-data/
  raw/bhavcopy/YYYY/YYYY-MM-DD.csv
  raw/fo_bhavcopy/…
  raw/full_bhavcopy/…
  raw/index_closes/…
  raw/bulk_deals/…  raw/block_deals/…  raw/fo_secban/…
  raw/corporate_actions/YYYY/YYYY-MM-DD.json
  raw/index_constituents/YYYY/YYYY-MM-DD_<index>.json
  manifest/downloads.jsonl
```

## Etiquette

Requests are throttled and an NSE session cookie is primed first. Keep date
ranges modest; `--skip-existing` is on by default. Exchange URLs can change
without notice.

This project does **not** download or ingest Kaggle (or other third-party) dumps.
If you only need rough historical OHLCV for experiments, fetch those yourself —
PowerNSE sticks to official archives.

## Documentation

| Guide | Link |
| --- | --- |
| [Install](https://inquilabee.github.io/powernse/user/install/) | pip / uv / clone |
| [Quick start](https://inquilabee.github.io/powernse/user/quickstart/) | Download + query |
| [Archives](https://inquilabee.github.io/powernse/user/download/archives/) | Every downloader |
| [NSEData](https://inquilabee.github.io/powernse/user/python/nsedata/) | Python API |
| [fetch-bundle](https://inquilabee.github.io/powernse/user/bundle/fetch-bundle/) | GitHub zip extract |
| [Publish](https://inquilabee.github.io/powernse/maintainer/publish/) | Maintainer release |

## Development

```bash
uv sync
make check    # ShipGate
make format
make test
make build
```

Local docs: `uv run --with mkdocs-material mkdocs serve`. Quality gates:
[ShipGate](https://inquilabee.github.io/shipgate/) (`suite: standard`).

## License

MIT — see [LICENSE](LICENSE).
