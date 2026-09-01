# NSE data archive

Tracked end-of-day archives refreshed from NSE exchange sources.

CM bhavcopy on this tree runs from **1994-11-03** (when NSE equity archives begin
hosting files) through the latest staged session. Weekdays before that, and
calendar gaps that return HTTP 404 from `nsearchives.nseindia.com`, are not
available from the exchange. Other series folders may still be empty placeholders
until a refresh fills them.

This tree may start with layout placeholders (`.gitkeep`) only. CSV/JSON payloads are added by the Sunday GitHub Actions refresh (or by maintainers running `powernse … --root ./nse-data` and committing). Until those files exist on GitHub, `fetch-bundle` will not yield OHLC bars — download from NSE locally instead.

A large local history under this directory can be `git add`ed when you are ready to publish; ~hundreds of MB is normal for multi-year CM bhavcopy.

## Layout

```text
raw/bhavcopy/
raw/fo_bhavcopy/
raw/full_bhavcopy/
raw/index_closes/
raw/bulk_deals/
raw/block_deals/
raw/fo_secban/
raw/corporate_actions/
raw/index_constituents/
manifest/
```

## Get a copy without cloning the whole repo

```bash
powernse fetch-bundle --force
# or
powernse fetch-bundle --repo inquilabee/powernse --dest ./nse-data --force
export POWERNSE_GITHUB_REPO=inquilabee/powernse
```

Prefer a Release asset (`--url …/nse-data-bundle/nse-data.zip`) when available — see
[fetch-bundle](https://inquilabee.github.io/powernse/user/bundle/fetch-bundle/).

## First time: backfill deep history

`--resume` only ever walks **forward** from today, so it cannot reach a source's
back-catalogue on a fresh (or thinly seeded) archive. Fill the leading gap once
with `--backfill` — from the source's known start up to your earliest staged
file (`--skip-existing` still applies):

```bash
powernse index-closes --backfill --root ./nse-data
```

Index closes start **2012-02-21** (`ind_close_all` 404s before that); a full
backfill is ~3,500 files / ~34 MB.

To reach **before** 2012-02-21 — per-index end-of-day levels back to the Nifty 50 base
date (1995-11-03) from NSE's historical API, merged into the same
`raw/index_closes/` files:

```bash
powernse index-history --root ./nse-data          # 24 long-history indices
powernse index-history --all --root ./nse-data     # every catalogued index (~2 min)
```

Per-index coverage before ~2000 is uneven (NSE serves what it has). Close-only
history rows are staged with open/high/low set equal to the close.

## Sunday refresh

Workflow `.github/workflows/refresh-nse-data.yml` resumes downloads (including corporate-actions and index-constituents) and commits updates. Locally:

```bash
powernse bhavcopy --resume --days 14 --root ./nse-data
powernse fo-bhavcopy --resume --days 14 --root ./nse-data
powernse index-closes --resume --days 14 --root ./nse-data
powernse index-history --root ./nse-data
powernse full-bhavcopy --resume --days 14 --root ./nse-data
powernse corporate-actions --from "$(date -u -d '14 days ago' +%F)" --to "$(date -u +%F)" --root ./nse-data
powernse index-constituents --date "$(date -u +%F)" --root ./nse-data
powernse bulk-deals --date "$(date -u +%F)" --root ./nse-data
powernse block-deals --date "$(date -u +%F)" --root ./nse-data
powernse fo-secban --date "$(date -u +%F)" --root ./nse-data
```
