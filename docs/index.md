# PowerNSE

<div class="pn-hero" markdown="0">
  <h1>Official NSE archives. On your disk.</h1>
  <p class="pn-tagline">
    One CLI and a small Python API for end-of-day equity data from the exchange —
    bhavcopy, F&amp;O, indexes, deals, corporate actions. No third-party dump ingest.
  </p>
  <p class="pn-actions">
    <a href="user/install/">Install</a>
    <a href="user/quickstart/">Quick start</a>
    <a class="pn-ghost" href="https://pypi.org/project/powernse/">PyPI</a>
    <a class="pn-ghost" href="https://github.com/inquilabee/powernse">GitHub</a>
  </p>
</div>

NSE URLs move. Session cookies are picky. PowerNSE stages the files under
`nse-data/`, keeps a download manifest, and lets you query OHLC without
re-learning the layout every quarter.

<div class="pn-grid" markdown="0">
  <div class="pn-card"><strong>Download from NSE</strong><span>Resume-friendly dated archives with throttling and skip-existing defaults.</span></div>
  <div class="pn-card"><strong>fetch-bundle</strong><span>Pull the tracked GitHub <code>nse-data/</code> tree as a zip when you want a ready archive.</span></div>
  <div class="pn-card"><strong>NSEData API</strong><span>OHLC, F&amp;O bars, index closes, deals, coverage gaps — from a few Python calls.</span></div>
  <div class="pn-card"><strong>Python 3.13+</strong><span><code>pip install powernse</code> · optional <code>powernse[pandas]</code> frames.</span></div>
</div>

## Try it

```bash
pip install powernse
powernse bhavcopy --resume
powernse fetch-bundle --force
powernse ohlc RELIANCE --from 2024-08-01 --to 2024-08-05
powernse doctor
```

```python
from datetime import date
from powernse import NSEData

data = NSEData("./nse-data")
bars = data.ohlc("RELIANCE", from_date=date(2024, 8, 1), to_date=date(2024, 8, 5))
```

## Guides

| | |
| --- | --- |
| [Install](user/install.md) | pip / uv / clone |
| [Quick start](user/quickstart.md) | Download and query |
| [Archives](user/download/archives.md) | Every downloader |
| [NSEData](user/python/nsedata.md) | Python API |
| [fetch-bundle](user/bundle/fetch-bundle.md) | GitHub zip extract |
| [Changelog](https://github.com/inquilabee/powernse/blob/main/CHANGELOG.md) | What shipped |
